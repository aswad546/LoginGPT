#!/bin/bash
MONITORING_PERIOD=500  # 5 minutes in seconds
CHECK_INTERVAL=15      # Check every 30 seconds
LOG_FILE="inactive_vllm_processes_threads.log"

echo "Continuously monitoring vllm processes and threads for inactivity..."

while true; do
    echo "$(date): Starting new monitoring cycle" >> $LOG_FILE
    
    # Create a temporary file to track CPU usage for this cycle
    TEMP_FILE=$(mktemp)
    
    # Initial snapshot of ALL vllm processes and threads (using -L flag for threads)
    ps -eLo pid,tid,ppid,%cpu,cmd | grep vllm | grep -v grep | awk '{print $1 ":" $2}' > $TEMP_FILE
    
    # Monitor for the specified duration
    END_TIME=$(($(date +%s) + MONITORING_PERIOD))
    while [ $(date +%s) -lt $END_TIME ]; do
        # Check each PID:TID's current CPU usage
        while read pid_tid; do
            PID=$(echo $pid_tid | cut -d':' -f1)
            TID=$(echo $pid_tid | cut -d':' -f2)
            CPU=$(ps -p $PID -T | awk -v tid=$TID '$2==tid {print $4}' 2>/dev/null || echo "999")
            if [[ $CPU != "0.0" && $CPU != "999" ]]; then
                # Process/thread is active, remove from tracking
                sed -i "/^$pid_tid$/d" $TEMP_FILE
            fi
        done < $TEMP_FILE
        
        sleep $CHECK_INTERVAL
    done
    
    # Show results for this cycle
    echo -e "\n$(date): Processes/threads inactive for last $((MONITORING_PERIOD/60)) minutes:" | tee -a $LOG_FILE
    echo "PID    TID    PPID   ETIME    TIME     %CPU   RSS      CMD" | tee -a $LOG_FILE
    echo "-------------------------------------------------------------------" | tee -a $LOG_FILE
    
    while read pid_tid; do
        PID=$(echo $pid_tid | cut -d':' -f1)
        TID=$(echo $pid_tid | cut -d':' -f2)
        # Show all threads and forks
        ps -p $PID -T -o pid,tid,ppid,etime,time,%cpu,rss,cmd | awk -v tid=$TID '$2==tid' 2>/dev/null
    done < $TEMP_FILE | tee -a $LOG_FILE
    
    # Cleanup temporary file
    rm $TEMP_FILE
    
    echo "----------------------------------------" | tee -a $LOG_FILE
    
    # Wait a bit before starting the next cycle
    sleep 60
done
EOF
