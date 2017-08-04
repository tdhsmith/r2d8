#! /bin/bash

for pid in $(pidof -x r2_supervisor.sh); do
    if [ $pid != $$ ]; then
      echo "Supervisor is still running, stopping myself (I am a replacement supervisor)"
      exit 0
    fi
done


function run_robot {
    echo "Starting r2d8"
    /usr/bin/python2 /home/r2d8/r2d8-scripts/artoodeeeight.py >> /home/r2d8/r2d8-scripts/logs/r2d8.log 2>&1
}


# to kill this app, kill the reboot script, then kill the app
until run_robot; do
    echo "Server 'artoodeeeight' crashed with exit code $?.  Respawning.." >&2
    sleep 1
done
