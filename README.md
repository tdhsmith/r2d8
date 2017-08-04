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

     python2 /home/r2d8/r2d8_scripts/artoodeeeight.py

To kill this app's process, (as you need to do when you update the code), type 

      ps -aux|grep artoodeeeight.py|grep -v grep

The numbers in the second column are the "Process Identifiers" or PIDs. 

You can pass a PID to the program "kill" to make it go away. So if the listed PID for artoodeeeight was 20392, then typing:

      kill 20392

Will make the artooodeeeight program stop running.

# Production (i.e. when you're not just testing it out)

When you run it "in production",  we use 2 layers to make it keep going.

The first one is a cron job. This means a program that the computer will run at a set time every day. You will schedule this task by typing (from the r2d8 directory with the source code):

      crontab etc/r2d8.crontab

This schedules *repeat* running of another program, called a supervisor script. That script is r2_supervisor.sh. This script when run checks to see if it is already running, and if so, self-terminates. Otherwise, it goes ahead and runs artoodeeeight for us. It *keeps* running r2d8 if r2d8 dies. 

When you need to work on r2, and the supervisor and crontab are running, first turn off the crontab schedule:

      crontab -r

This removes *all* cron jobs though for the user, so if you're on an account with multiple cron jobs, take that into account. 

Then kill the r2_supervisor.sh script similar to how you did with the artoodeeeight file:

       ps -aux|grep r2_supervisor.sh|grep -v grep|grep bash
       kill (whatever number)

Then kill artoodeeeight.py:

       ps -aux|grep artoodeeeight.py |grep -v grep  
       kill (whatever number)

Now you should be able to work on artoodeeeight.py with the service off. To turn the service back on, go:

       crontab etc/r2d8.crontab 

And then wait somewhere between 1 and 75 seconds for it to start working again. I suggest posting a test command in reddit somewhere and then r2d8 will catch the unread mention when it comes back on. 

# Logs

In addition to the app, you should run a log rotation program. To do so, type the following in the scripts folder 

logstatus -s logs/logstatus etc/logstatus.conf

This tells the program to rotate the logs when a certain critera is met. In our case, it's when a certain file size is reached. See the conf file for deatils and the documentation on the logstatus program. 