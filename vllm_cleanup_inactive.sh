#!/bin/bash
LOG_FILE="vllm_cleanup_decisions.log"

# First, just log what WOULD be cleaned up without actually doing it
echo "$(date): Starting safety check" >> $LOG_FILE

ps -eo pid,ppid,etime,time,%cpu,rss,cmd | grep vllm | grep -v grep | while read pid ppid etime time cpu rss cmd; do
    # Only consider processes that meet these criteria:
    # 1. 0% CPU currently (inactive right now)
    # 2. Running for more than 10 minutes
    # 3. Not the main vllm serve process
    # 4. Not the parent of any active process
    
    if [[ $cpu == "0.0" && ! $cmd =~ "vllm serve" ]]; then
        # Parse different etime formats
        if [[ $etime =~ ^([0-9]+):([0-9]+)$ ]]; then
            # Format: MM:SS
            minutes=${BASH_REMATCH[1]}
            if [ $minutes -ge 10 ]; then
                CHILDREN=$(pgrep -P $pid | wc -l)
                if [ $CHILDREN -eq 0 ]; then
                    echo "$(date): CANDIDATE for cleanup - PID: $pid, CMD: $cmd, ETIME: $etime, CPU_TIME: $time" >> $LOG_FILE
                    # Uncomment the next line only after you've reviewed the log and are confident
                    # kill -15 $pid
                else
                    echo "$(date): SKIPPING - PID: $pid has $CHILDREN children" >> $LOG_FILE
                fi
            fi
        elif [[ $etime =~ ^([0-9]+):([0-9]+):([0-9]+)$ ]]; then
            # Format: HH:MM:SS
            hours=${BASH_REMATCH[1]}
            minutes=${BASH_REMATCH[2]}
            total_minutes=$((hours * 60 + minutes))
            if [ $total_minutes -ge 10 ]; then
                CHILDREN=$(pgrep -P $pid | wc -l)
                if [ $CHILDREN -eq 0 ]; then
                    echo "$(date): CANDIDATE for cleanup - PID: $pid, CMD: $cmd, ETIME: $etime, CPU_TIME: $time" >> $LOG_FILE
                    # Uncomment the next line only after you've reviewed the log and are confident
                    # kill -15 $pid
                else
                    echo "$(date): SKIPPING - PID: $pid has $CHILDREN children" >> $LOG_FILE
                fi
            fi
        elif [[ $etime =~ ([0-9]+)-([0-9]+):([0-9]+):([0-9]+) ]]; then
            # Format: DD-HH:MM:SS
            days=${BASH_REMATCH[1]}
            hours=${BASH_REMATCH[2]}
            minutes=${BASH_REMATCH[3]}
            total_minutes=$((days * 1440 + hours * 60 + minutes))
            if [ $total_minutes -ge 10 ]; then
                CHILDREN=$(pgrep -P $pid | wc -l)
                if [ $CHILDREN -eq 0 ]; then
                    echo "$(date): CANDIDATE for cleanup - PID: $pid, CMD: $cmd, ETIME: $etime, CPU_TIME: $time" >> $LOG_FILE
                    # Uncomment the next line only after you've reviewed the log and are confident
                    # kill -15 $pid
                else
                    echo "$(date): SKIPPING - PID: $pid has $CHILDREN children" >> $LOG_FILE
                fi
            fi
        fi
    fi
done

# Also show summary of current vllm memory usage
echo "$(date): Current vllm memory usage:" >> $LOG_FILE
ps -eo rss,cmd | grep vllm | grep -v grep | awk '{sum+=$1} END {print "Total: " sum/1024/1024 " GB"}' >> $LOG_FILE
echo "----------------------------------------" >> $LOG_FILE
