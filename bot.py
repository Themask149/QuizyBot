import discord

from dotenv import load_dotenv
load_dotenv()
# Create an instance of a Client. This client represents your bot.
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Event that triggers when the bot has connected to Discord
@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

# Event that triggers when a message is sent in the server
@client.event
async def on_message(message):
    # Ignore messages sent by the bot itself
    if message.author == client.user:
        return

    # Check if the message starts with '!hello'
    if message.content.startswith('!hello'):
        await message.channel.send('Hello!')

# Run the bot with your token
client.run(dotenv.get('TOKEN'))
