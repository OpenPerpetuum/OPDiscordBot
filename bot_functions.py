# Utility commands to help with bot development.

import re
import json


def load_config(config_file):
    """Reads a JSON config file and returns it as a dict for setting up the bot and modules whhich require storage."""
    with open(config_file) as config:
        config_json = json.loads(config.read())
        return config_json


def get_channel(guild, target_channel_name):
    """Gets the target channel in the specified guild by name."""

    for channel in guild.text_channels:
        if channel.name == target_channel_name:
            return channel

    return None


def get_moderation_channel(message):
    """Returns the bot's moderation log channel for the guild the message is from.
       Returns None where a channel is not found."""

    mod_channel_name = 'mod-log'

    return get_channel(message.guild, mod_channel_name)


def find_single_user(username, guild):
    """Attempts to definitively find a single member in a guild. Used for commands that affect users, like bans.
       Returns None when it fails to do so. Takes a username and a guild as arguments."""

    found_users = find_members(username, guild.members)

    if found_users is not None and len(found_users) == 1:
        return found_users[0]

    else:
        return None


def find_members(search_query, member_list):
    """Function for finding a member by either their Discord name or their local nick. Case insensitive.
       Member_list is an iterable. Likely message.guild.users"""

    results = []

    for member in member_list:
        if str(search_query).lower() == str(member.name).lower() or \
                str(search_query).lower() == str(member.nick).lower() or \
                str(search_query).lower() == str(member.mention).lower():
            results.append(member)

    if len(results) is 0:
        return None

    return results


async def command_moderation_kick(message):
    """Moderation command. Kicks the target user from the target guild."""

    kick_message = "{0} Has kicked {1} from the server."

    target_user_search = re.match(r'!\w+ (\w+)', str(message.content))
    if target_user_search:
        target_user = find_single_user(target_user_search[1])
        if target_user is not None:
            mod_channel = get_moderation_channel(message)
            if mod_channel is not None:
                await mod_channel.send(kick_message.format(message.sender, target_user))
                await message.guild.kick(target_user)
