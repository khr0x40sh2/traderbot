# traderbot
Python "paper" trading bot using the Webull unofficial API

This is a very alpha release and may not have all of the required files at this time as I am working through cleaning up the code.

This bot requires the unofficial Webull API [https://github.com/tedchou12/webull] as well as a few other python packages. 
These packages can be found in requirements.txt

Credentials to webull should be supplied in the JSON file, "webull_credentials.json" or in the config.py file.
The symbol for the bot to use is also present in this config.py.
Please see https://github.com/tedchou12/webull/wiki for help with regards to login.

The bot uses a mysql database, the schema for the db and table can be found in traderbot.sql.
You will have to specify the user/password/hostname(or ip) in the db.py file.

The bot also ships with slack notification ability. This is commented out by default, and requires the SLACK_TOKEN and SLACK_CHANNEL values updated in the slackBot.py file.

The algorithm used by this bot is a simple RSI crossover algorithm and is intentionally simplistic.
Further updates may allow for multiple trading strategies to employed.

The bot notionally trades options at the ask and bid near the money, within accpetable user-defined minimum and maximum ask prices. 
Upon purchasing an option, the bot will log to a file and enter the trade into the database for record keeping.
Upon selling, the bot does the same.

DISCLAIMER:
This was created for educational/fun and carries 0 guarantees. Support is very limited on this project as it more "science project" than maintained software. 
Anything reflected in these files does not constitute and should not be taken as financial advise.
Use of this is at your own risk!
