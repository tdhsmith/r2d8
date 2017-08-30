These files are intended to be run from a directory on your computer called:

/home/r2d8/r2d8-scripts

# Databases

When run the bot creates two sqlite databases, one for BGG URL queries and one for keeping track of comments and responses. The default names are:

    UID-bot.db - the comment database
    UID-bgg.db - the BGG access cache database

where UID is the UID of the bot, usually "r2d8". 

Requirements:
 - PRAW 5.0
 - boardgamegeek
 - sqlite3 (included in most distributions, I think.)

To authorize this, you need to add keys from the app creation into the file ~/.config/praw.ini

Former people who've ran this bot will have those keys until you regenerate them. 


# Operation 

If you're manually trying to debug it, you can run the python file with

     python2 /home/r2d8/r2d8_scripts/artoodeeeight.py -l debug

# Production (i.e. when you're not just testing it out)

Run the bot on a systemd system. Copy r2d8.service to /lib/systemd/system (on Ubuntu 16) and enable the service via 'sudo systemctl enable r2d8.service'. You should be able to start/stop/status (and all the usual systemd commands) on the r2d8 service. 

To start the service: 'sudo systemctl start r2d8'.

The bot expects to be run from /home/r2d8/r2d8-scripts under the user 'r2d8'. If not is not the case, please update the r2d8.service file with the appropriate values. 
:
The logs for the service can be viewed in /var/log/syslog or via 'sudo journalctl -u r2d8'.
