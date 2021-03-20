from discord.ext import commands, tasks
import requests
import json
import os
import bot_functions
import discord
from time import strptime
from datetime import datetime, timedelta

# region Setup
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
# endregion Setup

# region Defaults

if 'killmail_channel' not in config_json:
    config_json['killmail_channel'] = 'op-general'
    print("Killmail channel not found in config file! Defaulting to #op-general")

if 'update_interval_seconds' not in config_json:
    config_json['update_interval_seconds'] = 300
    print("Killmail update interval not found in config file! Defaulting to 300 seconds.")


# endregion Defaults

# region Helper functions
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


def add_attacker_str(atk_saved_str: str, atk_to_add: json):
    if atk_to_add["hasKillingBlow"]:
        atk_saved_str = atk_saved_str + (
                "\n🕵️ **Agent**: " + str(atk_to_add['_embedded']['agent']['name']) + " - 🩸 Killing Blow! 🩸")
    else:
        atk_saved_str = atk_saved_str + ("\n🕵️ **Agent**: " + str(atk_to_add['_embedded']['agent']['name']))

    atk_saved_str = atk_saved_str + ("\n💠 **Corp**: " + str(atk_to_add['_embedded']['corporation']['name']) +
                                     "\n🤖 **Robot**: " + bot_name_lookup.get(
                atk_to_add['_embedded']['robot']['definition']) +
                                     "\n🗡️ **Damage Done**: " + str(prettier_numbers(atk_to_add['damageDealt'])))

    if int(atk_to_add['totalEcmAttempts']) > 0:
        atk_saved_str = atk_saved_str + "\n**ECM Attempts**: " + str(atk_to_add['totalEcmAttempts'])

    if int(atk_to_add['sensorSuppressions']) > 0:
        atk_saved_str = atk_saved_str + "\n**Sensor Supressions**: " + str(atk_to_add['sensorSuppressions'])

    if float(atk_to_add['energyDispersed']) > 0:
        atk_saved_str = atk_saved_str + "\n**Energy Drained**: " + str(prettier_numbers(atk_to_add['energyDispersed']))

    atk_saved_str = atk_saved_str + "\n "

    return atk_saved_str


def build_attacker_field(atkstr: str, embed: discord.embeds, atkfieldname: str):
    embed.add_field(name=atkfieldname,
                    value=str(atkstr),
                    inline=True)


def add_too_many_attackers(embed: discord.embeds):
    embed.add_field(name="Full Details",
                    value="Too many attackers to list, see the full details at the Killboard Link",
                    inline=False)
    return embed


def embed_linebreak():
    return "\n ──────────── "


# endregion Helper functions

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

        # Iterate over each new killmail
        for kill in new_killmails:

            # Embed Setup
            kill_message_embed = discord.Embed(title="Killboard Link",
                                               url="https://killboard.openperpetuum.com/kill/" + str(kill['id']),
                                               color=discord.colour.Color.random())
            kill_message_embed.set_author(name="Killmail #" + str(kill['id']),
                                          url="https://api.openperpetuum.com/killboard/kill/" + str(kill['id']))

            kill_message_embed.set_footer(text="Happened on " + str(kill['date']))

            # Embed - Target
            kill_message_embed.add_field(name="Target",
                                         value=str("🕵️ **Agent**: " + str(kill['_embedded']['agent']['name'])) +
                                               "\n💠 **Corp**: " + str(kill['_embedded']['corporation']['name']) +
                                               "\n🤖 **Robot**: " + bot_name_lookup.get(
                                             kill['_embedded']['robot']['definition']) +
                                               "\n🩹 **Damage Taken**: " + prettier_numbers(kill['damageReceived']) +
                                               "\n🗺️ **Zone**: " + str(
                                             kill['_embedded']['zone']['name']) + embed_linebreak(),
                                         inline=False)

            # Embed - Attacker(s) | Discord has some limitations when it comes to Embeds
            # More info: https://discordjs.guide/popular-topics/embeds.html#embed-limits

            # Setup for Attacker Field(s) for Embed
            atk_field_name = "⚔ Attackers"
            atkcount = (str(len(kill['_embedded']['attackers'])))
            if int(atkcount) <= 1:  # If there's only 1 attacker, change field name to singular.
                atk_field_name = "⚔ Attacker"

            atk_saved_list = ""  # Validated Attackers, saved to a list - These WILL exist in the embed
            current_atk_str = ""  # Validated Attackers + New Attacker we want to add - Check if this exceeds limits
            current_field_length = 0  # char-length of field we're currently manipulating
            embed_length = len(kill_message_embed)  # Embed char length, MAX 6000
            fields_built = len(kill_message_embed.fields)  # Keep track of total fields, MAX 25
            inline_next_attacker_field = False

            # Find Killing Blow and add to the list first
            for a in kill['_embedded']['attackers']:
                if a["hasKillingBlow"]:
                    atk_saved_list = add_attacker_str(atk_saved_list, a)
                    kill['_embedded']['attackers'].remove(a)  # Attacker has now been added, remove it from list
                    # Edge case, if there was only 1 attacker in total, we want to post the message
                    if len(kill['_embedded']['attackers']) == 0:
                        build_attacker_field(atk_saved_list, kill_message_embed, atk_field_name)
                    break

            # Validate the rest of the attackers
            for a in kill['_embedded']['attackers']:
                current_atk_str = add_attacker_str(atk_saved_list, a)  # Add a new Attackers info to the Saved list
                embed_length = len(kill_message_embed)  # Update current embed length
                new_length = len(current_atk_str) + embed_length

                if new_length >= 5800:  # Do we exceed the allowed Embed Length?
                    # End early, build what we have and add 'too many attackers' field at the end of the embed
                    build_attacker_field(atk_saved_list, kill_message_embed, atk_field_name)
                    add_too_many_attackers(kill_message_embed)  # Costs 1 field + ~85 characters
                    break
                else:
                    current_field_length = len(atk_saved_list)  # Update current field length
                    new_field_length = current_field_length + len(current_atk_str)
                    # If adding this attacker is still below field char limit
                    if (new_field_length <= 1024):  # Does adding this attacker exceed allowed Field char Length?
                        atk_saved_list = current_atk_str  # Add this attacker to the Saved List
                        # If this is the last Attacker to validate, build Embed
                        if a == kill['_embedded']['attackers'][-1]:
                            build_attacker_field(atk_saved_list, kill_message_embed, atk_field_name)

                    else:  # We exceeded the Field Length
                        if len(kill_message_embed.fields) >= 23:  # We exceeded the allowed amount of Fields
                            add_too_many_attackers(kill_message_embed)  # Costs 1 field + ~85 characters
                        else:  # We still have Fields to use, finish this Field and build a new one!
                            # Build field without adding latest attacker
                            build_attacker_field(atk_saved_list, kill_message_embed, atk_field_name)
                            atk_saved_list = ""  # Empty the list, since we just built a Full Field
                            atk_saved_list = add_attacker_str(atk_saved_list, a)  # Add the attacker we just skipped

            # Post the embed!
            for channel in channels:
                await channel.send(embed=kill_message_embed)

        return

    @display_new_kills.before_loop  # Ensures the killmail checker doesn't run before the bot can post.
    async def before_killmails(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(Killboard(bot))
    print("Killboard cog loaded.")
