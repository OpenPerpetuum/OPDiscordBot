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


def add_attacker(embed: discord.embeds, a: json):
    if a["hasKillingBlow"]:
        embed.add_field(name="⚔ Attacker - 🩸 Killing Blow! 🩸",
                        value=a['_embedded']['agent']['name'] +
                              "\n**Corp**: " + a['_embedded']['corporation']['name'],
                        inline=False)
    else:
        embed.add_field(name="⚔ Attacker",
                        value=a['_embedded']['agent']['name'] +
                              "\n**Corp**: " + a['_embedded']['corporation']['name'],
                        inline=False)

    embed.add_field(name="🤖 Robot",
                    value=bot_name_lookup.get(a['_embedded']['robot']['definition']),
                    inline=True)

    embed.add_field(name="🗡️ Damage dealt",
                    value=prettier_numbers(a['damageDealt']),
                    inline=True)

    if int(a['totalEcmAttempts']) > 0:
        embed.add_field(name="ECM Attempts",
                        value=a['totalEcmAttempts'],
                        inline=True)

    if int(a['sensorSuppressions']) > 0:
        embed.add_field(name="Sensor Supressions",
                        value=a['sensorSuppressions'],
                        inline=True)

    if float(a['energyDispersed']) > 0:
        embed.add_field(name="Energy Drained",
                        value=prettier_numbers(a['energyDispersed']),
                        inline=True)
    return embed


def add_too_many_attackers(embed: discord.embeds):
    embed.add_field(name="Full Details",
                    value="Too many attackers to list, see the full details at the Killboard Link",
                    inline=False)
    return embed


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
            # Test
            ijson = requests.get('https://api.openperpetuum.com/killboard/kill/2720')
            kill = json.loads(ijson.content)

            # Embed Setup
            kill_message_embed = discord.Embed(title="Killboard Link",
                                               url="https://killboard.openperpetuum.com/kill/" + str(kill['id']),
                                               color=discord.colour.Color.random())
            kill_message_embed.set_author(name="Killmail #" + str(kill['id']),
                                          url="https://api.openperpetuum.com/killboard/kill/" + str(kill['id']),
                                          icon_url="http://clipart-library.com/img/831510.png")  # TODO: Decide on icon
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
            # TODO: Embeds has a hard-limit on 25 fields
            # so if there is too many attackers or too many who did Drain/Supress/ECM
            # We need to shorten the list of attackers and put something like "... More attackers, check killboard link"
            # An example of this is with KillID: 2720
            # More info on embed limits: https://discordjs.guide/popular-topics/embeds.html#embed-limits

            field_overflow: bool = False
            field_count: int = 4  # We always start with 4 fields from the Victim section

            # Count the total amount of fields this Killmail would require
            for a in kill['_embedded']['attackers']:
                print("Field Check Start - " + str(field_count))
                field_count += 3  # At least we add 3 (Name, Robot, Damage as minimum)
                if int(a['totalEcmAttempts']) > 0:
                    field_count += 1
                if int(a['sensorSuppressions']) > 0:
                    field_count += 1
                if float(a['energyDispersed']) > 0:
                    field_count += 1
                print("Field Check End: - " + str(field_count))
            if (field_count > 25):
                field_overflow = True
                print("Found an Overflowing Kill ID: " + str(kill['id']))
                field_count = 4  # Reset value to reuse while building overflow embed

            # Do condensed attacker list, if Embed Field Count would go above the 25 MAX limit
            if (field_overflow):
                print("Entered FIELD OVERFLOW")

                # Find Killing Blow and put them first on the embed
                for a in kill['_embedded']['attackers']:
                    if a["hasKillingBlow"]:
                        add_attacker(kill_message_embed, a)
                        field_count += 3  # At least we add 3 (Name, Robot, Damage as minimum)
                        if int(a['totalEcmAttempts']) > 0:
                            field_count += 1

                        if int(a['sensorSuppressions']) > 0:
                            field_count += 1

                        if float(a['energyDispersed']) > 0:
                            field_count += 1
                        print("Added KB to embed, total fields: " + str(field_count))

                # Used to check if we are trying to add the final attacker when we hit the MAX field count of 25
                attacker_iteration: int = 1

                # Build remaining attacker(s) embeds
                for a in kill['_embedded']['attackers']:
                    if a["hasKillingBlow"]:
                        continue  # Do nothing, Killing Blow Attacker was already added earlier.
                    else:
                        # Count how many fields we want to add,
                        # check against field_count to make sure it fits within <=25 max limit
                        print("Attempting to add new attacker, Field count: " + str(field_count))
                        fields_to_add: int = 3  # At least we add 3 (Name, Robot, Damage as minimum)
                        if int(a['totalEcmAttempts']) > 0:
                            fields_to_add += 1
                        if int(a['sensorSuppressions']) > 0:
                            fields_to_add += 1
                        if float(a['energyDispersed']) > 0:
                            fields_to_add += 1
                        print("ATK Fields to add: " + str(fields_to_add))

                        temp_field_total = fields_to_add + field_count  # Would-be total if we added the above fields

                        print("Temp Total Fields: " + str(temp_field_total))

                        # If we do not reach the Field Limit with this entry, then add this attacker to the embed
                        if (temp_field_total <= 24):
                            print("RES: Less than 24, adding..")
                            add_attacker(kill_message_embed, a)
                            field_count = temp_field_total  # Save that we added new fields
                            print("NEW TOTAL: " + str(field_count))
                            attacker_iteration += 1

                        # If adding this entry would set our Field total = 25 (MAX) or less,
                        # AND its the last attacker for the kill then we add it,
                        # otherwise build the "More attackers... See Killboard for details"
                        elif temp_field_total <= 25 & attacker_iteration == len(kill)-1:
                            print("RES: <= 25 AND last entry, adding...")
                            add_attacker(kill_message_embed, a)
                            attacker_iteration += 1

                        else:
                            print("RES: OVERFLOW! Field Count atm: " + str(field_count))
                            print("RES: OVERFLOW! Too many attackers msg adding")
                            add_too_many_attackers(kill_message_embed)
                            break
            else:
                # This killmail requires less than 25 fields, so go ahead and add all of them

                # Find Killing Blow and put them first on the embed
                for a in kill['_embedded']['attackers']:
                    if a["hasKillingBlow"]:
                        add_attacker(kill_message_embed, a)

                for a in kill['_embedded']['attackers']:

                    if a["hasKillingBlow"]:
                        continue  # Already added the Killing Blow Entry
                    else:
                        add_attacker(kill_message_embed, a)

            # Post the embed!
            for channel in channels:
                print("-- POSTING EMBED MESSAGE --")
                await channel.send(embed=kill_message_embed)

        return

    @display_new_kills.before_loop  # Ensures the killmail checker doesn't run before the bot can post.
    async def before_killmails(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(Killboard(bot))
    print("Killboard cog loaded.")
