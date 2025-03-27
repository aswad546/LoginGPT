#!/bin/bash

# Function to clean up a specified directory inside the container
cleanup_dir() {
    local container="$1"
    local target_dir="$2"
    
    echo "Cleaning directory: ${target_dir}"
    
    # Check if the target directory exists in the container
    docker exec "$container" bash -c "test -d ${target_dir}" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "Target directory ${target_dir} does not exist in container ${container}."
        return
    fi

    # Attempt recursive deletion of all contents
    echo "Attempting recursive deletion of contents in ${target_dir}..."
    docker exec "$container" bash -c "rm -rf ${target_dir}/*" 2>/dev/null

    # Check if any files remain after recursive deletion
    files_remaining=$(docker exec "$container" bash -c "find ${target_dir} -type f | wc -l")
    if [ "$files_remaining" -gt 0 ]; then
        echo "Recursive deletion did not remove all files. Attempting individual file deletion..."
        docker exec "$container" bash -c "find ${target_dir} -type f -exec rm -f {} +"
        echo "Individual file deletion attempted in ${target_dir}."
    else
        echo "All files deleted recursively in ${target_dir}."
    fi

    echo "Finished cleaning ${target_dir}."
}

# Find the first running container whose name starts with "sso-monitor-worker"
container=$(docker ps --filter "name=sso-monitor-worker" --format "{{.Names}}" | head -n 1)

if [ -z "$container" ]; then
    echo "No container found with name starting with sso-monitor-worker."
    exit 1
fi

echo "Using container: $container"

# Define the directories to clean
directories=(
    "/app/modules/loginpagedetection/screenshot_flows"
    "/app/modules/loginpagedetection/output_images"
)

# Iterate over each directory and perform cleanup
for dir in "${directories[@]}"; do
    cleanup_dir "$container" "$dir"
done

echo "Deletion process complete."
