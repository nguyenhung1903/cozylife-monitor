import discord
import asyncio
import os
import logging
from datetime import datetime


class DiscordBotService:
    def __init__(self, token: str, channel_id: int, logger = None):
        self.token = token
        self.channel_id = channel_id
        self.logger=logger

    def send_discord_bot_message(self, message: str):
        class MyClient(discord.Client):
            async def on_ready(client):
                try:
                    channel = client.get_channel(self.channel_id)
                    if channel is None:
                        channel = await client.fetch_channel(self.channel_id)

                    await channel.send(message)

                    print(f"✅ Message successfully sent to channel " f"{self.channel_id}")
                    
                    if self.logger != None:
                        self.logger.info(f"✅ Message successfully sent to channel " f"{self.channel_id}")
                except discord.DiscordException as e:
                    print(f"❌ Discord error: {e}")
                    if self.logger != None:
                        self.logger.exception(f"❌ Discord error: {e}")

                finally:
                    await client.close()

        intents = discord.Intents.default()
        client = MyClient(intents=intents)
        client.run(self.token)
        
    def send_discord_bot_embed(self, embed: discord.Embed):
        class MyClient(discord.Client):
            async def on_ready(client):
                try:
                    channel = client.get_channel(self.channel_id)

                    if channel is None:
                        channel = await client.fetch_channel(self.channel_id)

                    await channel.send(embed=embed)

                    print("✅ System notification sent successfully")

                    if self.logger is not None:
                        self.logger.info("System notification sent successfully")

                except discord.DiscordException:
                    if self.logger is not None:
                        self.logger.exception("Discord notification failed")

                finally:
                    await client.close()

        intents = discord.Intents.default()
        client = MyClient(intents=intents)
        client.run(self.token)
    
    def send_message(self, message: str):
        self.send_discord_bot_message(message=message)
    
    def datetime_format(self,dt):
        new_dt = datetime.fromisoformat(dt)
        return new_dt
        
    def notify_shutdown_event(self, shutdown_time, startup_time):
        shutdown_time = self.datetime_format(shutdown_time)
        startup_time = self.datetime_format(startup_time)
        
        duration = startup_time - shutdown_time
        duration_seconds = int(duration.total_seconds())

        embed = discord.Embed(title="SYSTEM STATUS",color=discord.Color.dark_grey())

        embed.description = (
            f"The system went down "
            f"**{shutdown_time.strftime('%I:%M:%S %p')}**, "
            f"and restarted at "
            f"**{startup_time.strftime('%I:%M:%S %p')}**."
        )

        embed.add_field(name="Date",value=shutdown_time.strftime("%b %d, %Y"),inline=True)
        embed.add_field(name="Duration",value=f"`{duration_seconds} s`",inline=True)
        self.send_discord_bot_embed(embed)
        
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv("../.env")
    # log = logging.getLogger("smart_plug")
    discordBot = DiscordBotService(
        token=os.getenv("DISCORD_BOT_TOKEN"),
        channel_id=int(os.getenv("DISCORD_BOT_CHANNEL_ID")),
        # logger=log
    )
    discordBot.send_discord_bot_message( "Xin chào đây là tin nhắn test")

