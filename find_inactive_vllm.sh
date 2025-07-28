#!/bin/bash
DURATION=300  # 5 minutes in seconds
INTERVAL=30   # Check every 30 seconds
LOG_FILE="inactive_vllm_processes.log"

echo "Monitoring vllm processes for $((DURATION/60)) minutes to find inactive ones..."
echo "$(date): Starting monitoring" > $LOG_FILE

# Create a temporary file to track CPU usage
TEMP_FILE=$(mktemp)

# Initial snapshot of all vllm processes
ps -eo pid,%cpu,cmd | grep vllm | grep -v grep | awk '{print $1}' > $TEMP_FILE

# Monitor for the specified duration
END_TIME=$(($(date +%s) + DURATION))
while [ $(date +%s) -lt $END_TIME ]; do
    # Check each PID's current CPU usage
    while read pid; do
        CPU=$(ps -p $pid -o %cpu= 2>/dev/null || echo "999")
        if [[ $CPU != "0.0" && $CPU != "999" ]]; then
            # Process is active, remove from tracking
            sed -i "/^$pid$/d" $TEMP_FILE
        fi
    done < $TEMP_FILE
    
    sleep $INTERVAL
done

# Show results
echo -e "\nProcesses that have been inactive for $((DURATION/60)) minutes:"
echo "PID    ETIME    TIME     %CPU   RSS      CMD"
echo "--------------------------------------------------------"

while read pid; do
    ps -p $pid -o pid,etime,time,%cpu,rss,cmd 2>/dev/null | tail -n +2
done < $TEMP_FILE | tee -a $LOG_FILE

# Cleanup
rm $TEMP_FILE

# Generate kill commands
echo -e "\nKill commands for inactive processes:"
while read pid; do
    if [ ! -z "$pid" ]; then
        echo "kill -15 $pid"
    fi
done < <(awk '{print $1}' $LOG_FILE | tail -n +2)
