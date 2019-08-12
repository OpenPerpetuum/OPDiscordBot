# OPDiscordBot
A repository featuring discord bot(s) designed to consume OpenPerpetuum API(s) to display and interact with the Perpetuum Discord.

Depends on Discord.py and Requests.

# Setting it up

Create a new bot account through the Discord development portal (https://discordapp.com/developers/applications).
Place the token in the bot_config.json file, and invite the bot to a Discord server.

From there, it will check for, and post any new killmails that have arrived since its last posting. By default, it will post new killmails
to a text channel called #op-general every 300 seconds. This can be altered through the killboard_config.json file using the
"killmail_channel" and "update_interval_seconds" parameters respectively.
