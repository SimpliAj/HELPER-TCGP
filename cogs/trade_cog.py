import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import utils
from collections import defaultdict
from datetime import datetime, timezone

TRADEABLE_RARITIES = {
    "rainbow", "one star", "three diamond", "four diamond ex",
    "full art", "shiny", "shiny ex", "trainer", "gimmighoul",
}

RARITY_EMOJI = {
    "rainbow": "🌈", "crown": "👑", "one star": "⭐", "three diamond": "💎",
    "four diamond ex": "🔷", "full art": "🎨", "shiny": "✨", "shiny ex": "💫",
    "trainer": "🎓", "gimmighoul": "🪙", "god pack": "🌟",
}


def _re(rarity):
    return RARITY_EMOJI.get(rarity, "🃏")


def _rel_time(ts):
    diff = int(datetime.now(timezone.utc).timestamp()) - int(ts)
    if diff < 60:
        return f"{diff}s ago"
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    return f"{diff // 86400}d ago"


def _prepare_data(all_detections: list, show_all: bool) -> dict:
    """Returns {pack: {rarity: {card_name: [detections]}}} sorted newest-first."""
    by_pack = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for d in all_detections:
        rarity = d.get("rarity", "")
        if rarity not in TRADEABLE_RARITIES:
            continue
        if not show_all and d.get("traded"):
            continue
        pack = d.get("pack") or "unknown"
        card = d.get("card_name") or "Unknown Card"
        by_pack[pack][rarity][card].append(d)

    result = {}
    for pack in sorted(by_pack):
        result[pack] = {}
        for rarity in sorted(by_pack[pack]):
            cards = {}
            card_items = list(by_pack[pack][rarity].items())
            card_items.sort(key=lambda x: max(d.get("timestamp", 0) for d in x[1]), reverse=True)
            for card, dets in card_items:
                cards[card] = sorted(dets, key=lambda d: d.get("timestamp", 0), reverse=True)
            result[pack][rarity] = cards
    return result


def _pack_total(rarities: dict) -> int:
    return sum(len(dets) for cards in rarities.values() for dets in cards.values())


def _pack_display(pack: str) -> str:
    return pack.title() if pack != "unknown" else "❓ Unknown Pack"


# ── Level 1: Pack selection ──────────────────────────────────────────────────

class TradePackView(discord.ui.View):
    def __init__(self, data: dict, guild_id: str, show_all: bool):
        super().__init__(timeout=300)
        self.data = data
        self.guild_id = guild_id
        self.show_all = show_all
        self._rebuild()

    def _rebuild(self):
        self.clear_items()
        if self.data:
            options = []
            for pack, rarities in self.data.items():
                total = _pack_total(rarities)
                options.append(discord.SelectOption(
                    label=_pack_display(pack)[:100],
                    description=f"{total} card(s) · {len(rarities)} rarity type(s)",
                    value=pack,
                    emoji="📦",
                ))
            sel = discord.ui.Select(placeholder="Select a set/pack...", options=options[:25])
            sel.callback = self._on_select
            self.add_item(sel)

        toggle = discord.ui.Button(
            label="Show All" if not self.show_all else "Untraded Only",
            style=discord.ButtonStyle.primary,
        )
        refresh = discord.ui.Button(label="🔄", style=discord.ButtonStyle.secondary)
        toggle.callback = self._toggle
        refresh.callback = self._refresh
        self.add_item(toggle)
        self.add_item(refresh)

    async def _on_select(self, interaction: discord.Interaction):
        pack = interaction.data["values"][0]
        view = TradeRarityView(pack, self.data[pack], self.data, self.guild_id, self.show_all)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _toggle(self, interaction: discord.Interaction):
        self.show_all = not self.show_all
        dets = await asyncio.to_thread(utils.load_detections, self.guild_id)
        self.data = _prepare_data(dets, self.show_all)
        self._rebuild()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _refresh(self, interaction: discord.Interaction):
        dets = await asyncio.to_thread(utils.load_detections, self.guild_id)
        self.data = _prepare_data(dets, self.show_all)
        self._rebuild()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    def _build_embed(self) -> discord.Embed:
        mode = "All" if self.show_all else "Untraded"
        embed = discord.Embed(title=f"🃏 Trade Cards — {mode}", color=discord.Color.blurple())
        if not self.data:
            embed.description = "No detections found."
            return embed
        lines = []
        for pack, rarities in self.data.items():
            total = _pack_total(rarities)
            rarity_parts = " · ".join(
                f"{_re(r)}{sum(len(d) for d in cards.values())}"
                for r, cards in rarities.items()
            )
            lines.append(f"**{_pack_display(pack)}** — {total} card(s)\n{rarity_parts}")
        embed.description = "\n\n".join(lines)
        return embed


# ── Level 2: Rarity selection ─────────────────────────────────────────────────

class TradeRarityView(discord.ui.View):
    def __init__(self, pack: str, rarities: dict, all_data: dict, guild_id: str, show_all: bool):
        super().__init__(timeout=300)
        self.pack = pack
        self.rarities = rarities
        self.all_data = all_data
        self.guild_id = guild_id
        self.show_all = show_all
        self._rebuild()

    def _rebuild(self):
        self.clear_items()
        options = []
        for rarity, cards in self.rarities.items():
            count = sum(len(dets) for dets in cards.values())
            options.append(discord.SelectOption(
                label=rarity.title()[:100],
                description=f"{count} card(s)",
                value=rarity,
                emoji=_re(rarity),
            ))
        if options:
            sel = discord.ui.Select(placeholder="Select a rarity...", options=options[:25])
            sel.callback = self._on_select
            self.add_item(sel)

        back = discord.ui.Button(label="⬅ Packs", style=discord.ButtonStyle.secondary)
        back.callback = self._back
        self.add_item(back)

    async def _on_select(self, interaction: discord.Interaction):
        rarity = interaction.data["values"][0]
        cards = self.rarities[rarity]
        view = TradeCardListView(self.pack, rarity, cards, self.rarities, self.all_data, self.guild_id, self.show_all)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _back(self, interaction: discord.Interaction):
        parent = TradePackView(self.all_data, self.guild_id, self.show_all)
        await interaction.response.edit_message(embed=parent._build_embed(), view=parent)

    def _build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"📦 {_pack_display(self.pack)}",
            color=discord.Color.blurple(),
        )
        lines = []
        for rarity, cards in self.rarities.items():
            count = sum(len(dets) for dets in cards.values())
            lines.append(f"{_re(rarity)} **{rarity.title()}** — {count} card(s)")
        embed.description = "\n".join(lines)
        return embed


# ── Level 3: Card list ────────────────────────────────────────────────────────

class TradeCardListView(discord.ui.View):
    def __init__(self, pack: str, rarity: str, cards: dict, rarities: dict, all_data: dict, guild_id: str, show_all: bool):
        super().__init__(timeout=300)
        self.pack = pack
        self.rarity = rarity
        self.cards = cards  # {card_name: [detections]}
        self.rarities = rarities
        self.all_data = all_data
        self.guild_id = guild_id
        self.show_all = show_all
        self._rebuild()

    def _rebuild(self):
        self.clear_items()
        options = []
        for name, dets in list(self.cards.items())[:25]:
            count = len(dets)
            ts = dets[0].get("timestamp", 0)
            options.append(discord.SelectOption(
                label=(name + (f" ×{count}" if count > 1 else ""))[:100],
                description=_rel_time(ts),
                value=name[:100],
                emoji=_re(self.rarity),
            ))
        if options:
            sel = discord.ui.Select(placeholder="Select a card...", options=options)
            sel.callback = self._on_select
            self.add_item(sel)

        back = discord.ui.Button(label="⬅ Rarities", style=discord.ButtonStyle.secondary)
        back.callback = self._back
        self.add_item(back)

    async def _on_select(self, interaction: discord.Interaction):
        card_name = interaction.data["values"][0].split(" ×")[0]  # strip "×N" suffix if present
        # Find the actual key (handle ×N suffix edge case)
        dets = self.cards.get(card_name) or next(
            (d for n, d in self.cards.items() if n == card_name), []
        )
        view = TradeCardDetailView(card_name, self.rarity, dets, self.pack, self.rarities, self.all_data, self.guild_id, self.show_all)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _back(self, interaction: discord.Interaction):
        view = TradeRarityView(self.pack, self.rarities, self.all_data, self.guild_id, self.show_all)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    def _build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"{_re(self.rarity)} {self.rarity.title()} — {_pack_display(self.pack)}",
            color=discord.Color.blurple(),
        )
        lines = []
        for name, dets in self.cards.items():
            count = len(dets)
            ts = dets[0].get("timestamp", 0)
            lines.append(f"**{name}**" + (f" ×{count}" if count > 1 else "") + f" · {_rel_time(ts)}")
        embed.description = "\n".join(lines) or "No cards."
        return embed


# ── Level 4: Card detail ──────────────────────────────────────────────────────

class TradeCardDetailView(discord.ui.View):
    def __init__(self, card_name: str, rarity: str, detections: list, pack: str, rarities: dict, all_data: dict, guild_id: str, show_all: bool):
        super().__init__(timeout=300)
        self.card_name = card_name
        self.rarity = rarity
        self.detections = list(detections)
        self.pack = pack
        self.rarities = rarities
        self.all_data = all_data
        self.guild_id = guild_id
        self.show_all = show_all
        self.detection = detections[0] if detections else {}

        if self.detection.get("message_link"):
            self.add_item(discord.ui.Button(
                label="🔗 Jump",
                style=discord.ButtonStyle.link,
                url=self.detection["message_link"],
            ))

    @discord.ui.button(label="📎 Send XML", style=discord.ButtonStyle.secondary)
    async def send_xml(self, interaction: discord.Interaction, button: discord.ui.Button):
        xml_url = self.detection.get("xml_url")
        if not xml_url:
            await interaction.response.send_message("❌ No XML file.", ephemeral=True)
            return
        await interaction.response.send_message(f"📎 XML: {xml_url}", ephemeral=True)

    @discord.ui.button(label="✅ Mark as Traded", style=discord.ButtonStyle.success)
    async def mark_traded(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.detection.get("traded"):
            await interaction.response.send_message("Already traded.", ephemeral=True)
            return
        await asyncio.to_thread(utils.mark_detection_traded, self.guild_id, self.detection["id"])
        self.detection["traded"] = True
        button.disabled = True
        button.label = "✅ Traded"
        self.detections = [d for d in self.detections if not d.get("traded")]
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.button(label="⬅ Back", style=discord.ButtonStyle.primary)
    async def go_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        dets = await asyncio.to_thread(utils.load_detections, self.guild_id)
        data = _prepare_data(dets, self.show_all)
        rarities = data.get(self.pack, self.rarities)
        cards = rarities.get(self.rarity, {})
        view = TradeCardListView(self.pack, self.rarity, cards, rarities, data, self.guild_id, self.show_all)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    def _build_embed(self) -> discord.Embed:
        emoji = _re(self.rarity)
        count = len(self.detections)
        ts = int(self.detection.get("timestamp", 0))
        traded = self.detection.get("traded", False)
        embed = discord.Embed(
            title=f"{emoji} {self.card_name}",
            color=discord.Color.green() if traded else discord.Color.blurple(),
        )
        embed.add_field(name="Rarity", value=self.rarity.title(), inline=True)
        embed.add_field(name="Set", value=_pack_display(self.pack), inline=True)
        embed.add_field(name="Available", value=f"×{count}", inline=True)
        embed.add_field(name="Last Seen", value=f"<t:{ts}:F>", inline=True)
        embed.add_field(name="Status", value="✅ Traded" if traded else "🔄 Available", inline=True)
        if self.detection.get("xml_url"):
            embed.add_field(name="XML", value="✅", inline=True)
        return embed


class TradeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="trade", description="Browse detected cards available for trade")
    async def trade(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild.id)
        all_dets = await asyncio.to_thread(utils.load_detections, guild_id)
        data = _prepare_data(all_dets, show_all=False)
        view = TradePackView(data, guild_id, show_all=False)
        await interaction.followup.send(embed=view._build_embed(), view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TradeCog(bot))
