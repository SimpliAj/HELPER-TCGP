import json
import os
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

import utils

# Weekly per-server report (2026-10-26): Sundays 18:00 UTC, posted to the server's god pack channel, only when the
# server relayed something that week. Counts are the delta of the lifetime stats against last week's snapshot
# (promo_state.json). Switch: promo.json "weekly_report": false; per server: promo.json "disabled_guilds".
STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "promo_state.json")
REPORT_WEEKDAY, REPORT_HOUR = 6, 18


def _load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"snapshots": {}, "last_week": None}


def _save_state(state):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_PATH)


def _totals(cfg):
    st = cfg.get("stats") or {}
    return int((st.get("godpacks") or {}).get("total", 0)), int((st.get("general") or {}).get("total", 0))


class PromoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.weekly_report.start()

    def cog_unload(self):
        self.weekly_report.cancel()

    async def _run(self, force_week=None):
        promo = utils._promo_cfg()
        if not promo.get("weekly_report", True) or not promo.get("enabled"):
            return 0
        state = _load_state()
        week = force_week or datetime.now(timezone.utc).strftime("%G-W%V")
        if state.get("last_week") == week:
            return 0
        sent = 0
        for guild in self.bot.guilds:
            gid = str(guild.id)
            cfg = utils.load_guild_config(gid)
            gp, gen = _totals(cfg)
            prev = state["snapshots"].get(gid)
            state["snapshots"][gid] = [gp, gen]
            if prev is None or not utils._promo_active(gid):
                continue
            d_gp, d_gen = max(0, gp - prev[0]), max(0, gen - prev[1])
            if d_gp + d_gen == 0:
                continue
            ch_id = ((cfg.get("keyword_channel_map") or {}).get("god pack") or {}).get("channel_id")
            channel = self.bot.get_channel(int(ch_id)) if ch_id else None
            if not channel:
                continue
            embed = discord.Embed(
                title="📊 Your week in packs",
                description=f"**{d_gp}** god pack{'s' if d_gp != 1 else ''} and **{d_gen}** other hit{'s' if d_gen != 1 else ''} relayed in this server this week.",
                color=discord.Color.gold(),
            )
            block = promo.get("weekly_block")
            if block:
                embed.add_field(name="\u200b", value=block, inline=False)
            embed.set_footer(text="Provided by Team G ¦ HELPER TCGP Discord Bot", icon_url="https://imgur.com/T0KX069.png")
            try:
                await channel.send(embed=embed, view=utils.add_promo_button(None, gid))
                sent += 1
            except Exception as e:
                print(f"[promo-weekly] send failed for {gid}: {e}")
        state["last_week"] = week
        _save_state(state)
        print(f"[promo-weekly] {week}: sent {sent} report(s)")
        return sent

    @tasks.loop(minutes=30)
    async def weekly_report(self):
        now = datetime.now(timezone.utc)
        state = _load_state()
        if not state.get("snapshots"):
            await self._run(force_week="baseline")  # first start: snapshot only, nothing to compare yet
            return
        if now.weekday() == REPORT_WEEKDAY and now.hour == REPORT_HOUR:
            await self._run()

    @weekly_report.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(PromoCog(bot))
