#!/bin/bash
LOG_FILE="vllm_cleanup_decisions.log"

# First, just log what WOULD be cleaned up without actually doing it
echo "$(date): Starting safety check" >> $LOG_FILE

ps -eo pid,ppid,etime,time,%cpu,rss,cmd | grep vllm | grep -v grep | while read pid ppid etime time cpu rss cmd; do
    # Only consider processes that meet ALL these criteria:
    # 1. 0% CPU
    # 2. 00:00:00 accumulated CPU time
    # 3. Running for more than 4 hours
    # 4. Not the main vllm serve process
    # 5. Not the parent of any active process
    
    if [[ $cpu == "0.0" && $time == "00:00:00" && ! $cmd =~ "vllm serve" ]]; then
        if [[ $etime =~ ([0-9]+)-([0-9]+):([0-9]+):([0-9]+) ]]; then
            days=${BASH_REMATCH[1]}
            hours=${BASH_REMATCH[2]}
            if [ $days -gt 0 ] || [ $minutes -gt 8 ]; then
                # Check if this process has any children
                CHILDREN=$(pgrep -P $pid | wc -l)
                if [ $CHILDREN -eq 0 ]; then
                    echo "$(date): CANDIDATE for cleanup - PID: $pid, CMD: $cmd, ETIME: $etime" >> $LOG_FILE
                    # Uncomment the next line only after you've reviewed the log and are confident
                    # kill -15 $pid
                else
                    echo "$(date): SKIPPING - PID: $pid has $CHILDREN children" >> $LOG_FILE
                fi
            fi
        fi
    fi
done
