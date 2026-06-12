import asyncio
import os

import discord
from discord.ext import commands
import wavelink

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
LAVALINK_URI = os.environ.get("LAVALINK_URI", "http://127.0.0.1:2333")
LAVALINK_PASSWORD = os.environ.get("LAVALINK_PASSWORD", "youshallnotpass")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def setup_hook():
    node = wavelink.Node(uri=LAVALINK_URI, password=LAVALINK_PASSWORD)

    # محاولات إعادة الاتصال في حال Lavalink لسه يقلع (يحتاج وقت أطول من البوت)
    for attempt in range(10):
        try:
            await wavelink.Pool.connect(nodes=[node], client=bot)
            break
        except Exception as e:
            print(f"تعذر الاتصال بـ Lavalink (محاولة {attempt + 1}/10): {e}")
            await asyncio.sleep(5)


@bot.event
async def on_ready():
    print(f"تم تسجيل الدخول كـ {bot.user}")


@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    print(f"✅ متصل بعقدة Lavalink: {payload.node.identifier}")


@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    player = payload.player
    if not player:
        return
    channel = getattr(player, "home", None)
    if channel:
        await channel.send(f"🎶 يتم الآن تشغيل: **{payload.track.title}**")


@bot.command(name="join")
async def join(ctx: commands.Context):
    if ctx.author.voice is None:
        await ctx.send("لازم تكون داخل قناة صوتية أولاً.")
        return

    channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        player: wavelink.Player = await channel.connect(cls=wavelink.Player)
        player.autoplay = wavelink.AutoPlayMode.partial
        player.home = ctx.channel
    else:
        await ctx.voice_client.move_to(channel)

    await ctx.send(f"تم الانضمام إلى {channel.name}")


@bot.command(name="play")
async def play(ctx: commands.Context, *, query: str):
    if ctx.voice_client is None:
        if ctx.author.voice is None:
            await ctx.send("لازم تكون داخل قناة صوتية أولاً.")
            return
        player: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        player.autoplay = wavelink.AutoPlayMode.partial
        player.home = ctx.channel
    else:
        player: wavelink.Player = ctx.voice_client

    search = query if query.startswith("http") else f"ytsearch:{query}"

    async with ctx.typing():
        tracks: wavelink.Search = await wavelink.Playable.search(search)

    if not tracks:
        await ctx.send("ما لقيت أي نتيجة لهذا البحث.")
        return

    if isinstance(tracks, wavelink.Playlist):
        added = await player.queue.put_wait(tracks)
        await ctx.send(f"✅ تمت إضافة قائمة التشغيل **{tracks.name}** ({added} مقطع) للقائمة.")
    else:
        track = tracks[0]
        await player.queue.put_wait(track)
        if player.playing:
            await ctx.send(f"✅ تمت الإضافة للقائمة: **{track.title}**")

    if not player.playing:
        await player.play(player.queue.get())


@bot.command(name="skip")
async def skip(ctx: commands.Context):
    player: wavelink.Player = ctx.voice_client
    if player and player.playing:
        await player.skip(force=True)
        await ctx.send("⏭️ تم التخطي.")
    else:
        await ctx.send("لا يوجد شيء قيد التشغيل.")


@bot.command(name="pause")
async def pause(ctx: commands.Context):
    player: wavelink.Player = ctx.voice_client
    if player and player.playing and not player.paused:
        await player.pause(True)
        await ctx.send("⏸️ تم الإيقاف المؤقت.")


@bot.command(name="resume")
async def resume(ctx: commands.Context):
    player: wavelink.Player = ctx.voice_client
    if player and player.paused:
        await player.pause(False)
        await ctx.send("▶️ تم الاستئناف.")


@bot.command(name="queue")
async def queue_cmd(ctx: commands.Context):
    player: wavelink.Player = ctx.voice_client
    if not player or player.queue.is_empty:
        await ctx.send("القائمة فارغة.")
        return

    msg = "\n".join(f"{i + 1}. {t.title}" for i, t in enumerate(player.queue))
    await ctx.send(f"📜 القائمة:\n{msg}")


@bot.command(name="stop")
async def stop(ctx: commands.Context):
    player: wavelink.Player = ctx.voice_client
    if player:
        player.queue.clear()
        await player.disconnect()
    await ctx.send("⏹️ تم الإيقاف ومسح القائمة.")


@bot.command(name="leave")
async def leave(ctx: commands.Context):
    player: wavelink.Player = ctx.voice_client
    if player:
        await player.disconnect()
        await ctx.send("تم الخروج من القناة الصوتية.")


bot.run(DISCORD_TOKEN)
