from discord.ext import commands, tasks
import requests
import json
import os
import bot_functions
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

        if raw_data.status_code is not 200:  # If the API request was unsuccessful, stop.
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

        raw_kill_message = "=============New Kill!================\n" \
                           "Victim: {0}\n" \
                           "Zone: {1}\n" \
                           "Corporation: {2}\n" \
                           "Date: {3}\n" \
                           "Robot: {4}\n" \
                           "\n" \
                           "Attackers: \n{5}\n"
        for kill in new_killmails:
            attackers_text = ""
            for a in kill['_embedded']['attackers']:
                attack_text = "Agent: {0}, Robot: {1}, Damage: {2}".format(
                    a['_embedded']['agent']['name'],
                    bot_name_lookup.get(a['_embedded']['robot']['definition'], a['_embedded']['robot']['definition']),
                    a['damageDealt'],
                )

                if int(a['totalEcmAttempts']) > 0:
                    attack_text += ", {} ECM".format(
                        a['totalEcmAttempts'],
                    )
                if int(a['sensorSuppressions']) > 0:
                    attack_text += ", {} SS".format(
                        a['sensorSuppressions'],
                    )

                if float(a['energyDispersed']) > 0:
                    attack_text += ", {} Accum drained".format(
                        a['energyDispersed'],
                    )

                if a["hasKillingBlow"]:
                    attack_text += " Killing Blow!"

                attackers_text += attack_text + "\n"

            kill_message = raw_kill_message.format(
                kill['_embedded']['agent']['name'],
                kill['_embedded']['zone']['name'],
                kill['_embedded']['corporation']['name'],
                kill['date'],
                bot_name_lookup.get(kill['_embedded']['robot']['definition'], kill['_embedded']['robot']['definition']),
                attackers_text)

            for channel in channels:
                await channel.send(kill_message)

        return

    @display_new_kills.before_loop  # Ensures the killmail checker doesn't run before the bot can post.
    async def before_killmails(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(Killboard(bot))
    print("Killboard cog loaded.")
