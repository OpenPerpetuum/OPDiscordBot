from discord.ext import commands, tasks
import requests
import json
import os
import bot_functions
import discord
from time import strptime
from datetime import datetime, timedelta

API_URL = 'https://api.openperpetuum.com/killboard/kill?order-by[0][type]=field&order-by[0][field]=' \
          'date&order-by[0][direction]=desc'

KILLBOARD_URL = 'https://killboard.openperpetuum.com/kill/'  # Initially placed in because I thought that links could
# be generated. However, the OP killboard page doesn't allow for direct linking.
CONFIG_FILE = os.path.join(os.path.abspath(os.curdir), 'config/killboard_config.json')
KILLBOARD_CONFIG = 'cogs/config/killboard_config.json'
BOT_NAME_FILE = 'cogs/config/bot_definition_map.json'

TIME_PARSE_STRING = '%Y-%m-%d %H:%M:%S'

config_json = bot_functions.load_config(KILLBOARD_CONFIG)
bot_name_lookup = bot_functions.load_config(BOT_NAME_FILE)

# Defaults

if 'killmail_channel' not in config_json:
    config_json['killmail_channel'] = 'op-general'
    print("Killmail channel not found in config file! Defaulting to #op-general")

if 'update_interval_seconds' not in config_json:
    config_json['update_interval_seconds'] = 300
    print("Killmail update interval not found in config file! Defaulting to 300 seconds.")


def get_last_kill_time():
    """Returns a struct_time object with the last saved kill. """
    global config_json  # Update the JSON in memory while we're reading the last time.
    config_json = bot_functions.load_config(KILLBOARD_CONFIG)
    if 'last_kill' in config_json:
        return strptime(config_json['last_kill']['date'], TIME_PARSE_STRING)
    else:
        return (datetime.now() - timedelta(hours=96)).timetuple()  # If there's no time in the config, default to
    #  the current time minus an hour.


def prettier_numbers(number: int):
    x = str(number)
    pretty = x.split('.')
    return pretty[0]


class Killboard(commands.Cog):
    """Prototype Perpetuum killboard cog"""

    def __init__(self, bot):
        self.bot = bot
        self.display_new_kills.start()

    @tasks.loop(seconds=config_json['update_interval_seconds'])
    async def display_new_kills(self):
        """This module checks the OpenPerpetuum API regularly for new kills. If kills are found, it will post them,
        along with a web link."""

        channels = []

        for guild in self.bot.guilds:  # For all of the places we're in, check if there's an op-general channel
            search = bot_functions.get_channel(guild, config_json['killmail_channel'])
            if search is not None:
                channels.append(search)  # If we find one, put it in the list.

        if len(channels) == 0:  # If there's no valid channels, there is no point in carrying on.
            print("The bot is not in any servers with an #op-general channel.")
            return

        print("Fetching new killmails.")

        last_kill_time = get_last_kill_time()

        try:
            raw_data = requests.get(API_URL)
        except Exception as ex:
            print("Exception {0} occurred while trying to fetch killmails.".format(ex))
            return

        if raw_data.status_code != 200:  # If the API request was unsuccessful, stop.
            print("Status {0} returned while trying to fetch killmails.".format(raw_data.status_code))
            return

        parsed_data = json.loads(raw_data.content)['_embedded']['kill']

        new_killmails = []

        for raw_kill in parsed_data:  # If the killmails are more recent than whatever we last posted, use them.
            currdate = strptime(raw_kill['date'], TIME_PARSE_STRING)
            if currdate > last_kill_time:
                new_killmails.append(raw_kill)

        print("Found {0} new killmails.".format(len(new_killmails)))

        if len(new_killmails) == 0:  # If there's no new killmails
            return  # Do nothing.

        with open(KILLBOARD_CONFIG, 'w') as config:  # Write the most recent timestamp to our file
            config_json['last_kill'] = {
                "date": new_killmails[0]['date'],
                "uid": new_killmails[0]['uid']
            }

            config.write(json.dumps(config_json))

        # Iterate over Attacker(s)
        for kill in new_killmails:
            # Embed Setup
            kill_message_embed = discord.Embed(title="Killboard Link",
                                               url="https://killboard.openperpetuum.com/kill/" + str(kill['id']),
                                               color=discord.colour.Color.random())
            kill_message_embed.set_author(name="Killmail #" + str(kill['id']),
                                          url="https://api.openperpetuum.com/killboard/kill/" + str(kill['id']),
                                          icon_url="http://clipart-library.com/img/831510.png")
            # kill_message_embed.set_thumbnail(
            #     url="http://clipart-library.com/img/831510.png")  # TODO: Fetch Victims robot picture, or Corp icons?

            kill_message_embed.set_footer(text="Happened on " + str(kill['date']))

            # Embed - Victim
            kill_message_embed.add_field(name="Victim",
                                         value=str(kill['_embedded']['agent']['name']) +
                                               "\n**Corp**: " + str(kill['_embedded']['corporation']['name']),
                                         inline=True)

            kill_message_embed.add_field(name="🤖 Robot",
                                         value=bot_name_lookup.get(kill['_embedded']['robot']['definition']),
                                         inline=False)

            kill_message_embed.add_field(name="🩹 Damage Taken",
                                         value=prettier_numbers(kill['damageReceived']),
                                         inline=True)

            kill_message_embed.add_field(name="🗺️ Zone",
                                         value=kill['_embedded']['zone']['name'],
                                         inline=True)

            # Embed - Attacker(s)
            for a in kill['_embedded']['attackers']:

                if a["hasKillingBlow"]:
                    kill_message_embed.add_field(name="⚔ Attacker - 🩸 Killing Blow! 🩸",
                                                 value=a['_embedded']['agent']['name'] +
                                                       "\n**Corp**: " + a['_embedded']['corporation']['name'],
                                                 inline=False)
                else:
                    kill_message_embed.add_field(name="⚔ Attacker",
                                                 value=a['_embedded']['agent']['name'] +
                                                       "\n**Corp**: " + a['_embedded']['corporation']['name'],
                                                 inline=False)

                kill_message_embed.add_field(name="🤖 Robot",
                                             value=bot_name_lookup.get(a['_embedded']['robot']['definition']),
                                             inline=True)

                kill_message_embed.add_field(name="🗡️ Damage dealt",
                                             value=prettier_numbers(a['damageDealt']),
                                             inline=True)

                if int(a['totalEcmAttempts']) > 0:
                    kill_message_embed.add_field(name="ECM Attempts",
                                                 value=a['totalEcmAttempts'],
                                                 inline=True)

                if int(a['sensorSuppressions']) > 0:
                    kill_message_embed.add_field(name="Sensor Supressions",
                                                 value=a['sensorSuppressions'],
                                                 inline=True)

                if float(a['energyDispersed']) > 0:
                    kill_message_embed.add_field(name="Accum Drained",
                                                 value=a['energyDispersed'],
                                                 inline=True)

            for channel in channels:
                await channel.send(embed=kill_message_embed)

            return

    @display_new_kills.before_loop  # Ensures the killmail checker doesn't run before the bot can post.
    async def before_killmails(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(Killboard(bot))
    print("Killboard cog loaded.")
