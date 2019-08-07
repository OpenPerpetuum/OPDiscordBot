import discord
from discord.ext import commands
from bot_functions import load_config

CONFIG_FILE = 'bot_config.json'
CONFIG_TOKEN = 'Bot Token'

config_json = load_config(CONFIG_FILE)
TOKEN = config_json[CONFIG_TOKEN]  # Loads the bot's token from a configuration file.


def get_prefix(bot, message):

    prefixes = ['!']

    # If we are in a guild, we allow for the user to mention us or use any of the prefixes in our list.
    return commands.when_mentioned_or(*prefixes)(bot, message)


extensions = ['cogs.perpetuum_killboard_cog']
# The bot modules we wish to load. The dot represents folders.

bot = commands.Bot(command_prefix=get_prefix, description='NetMarble Bot Test')

for extension in extensions:
    try:
        bot.load_extension(extension)
    except Exception as e:
        print(f'Failed to load extension {extension}.')


@bot.event
async def on_ready():
    print(f'\nLogged in as: {bot.user.name} - {bot.user.id}\nVersion: {discord.__version__}\n')

    print(f'Successfully logged in and booted...!')


bot.run(TOKEN, bot=True, reconnect=True)
