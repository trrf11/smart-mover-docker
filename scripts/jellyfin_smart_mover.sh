#!/bin/bash

#########################################
##        Jellyfin Smart Mover        ##
#########################################
#
# Description: Moves media files from cache to array based on Jellyfin playback status
# Author: Tim Fokker
# Version: 1.1.0
# Date: 2024-02-21

SCRIPT_VERSION="1.2.0"
#
# Requirements:
# - jq: Install through Community Applications -> NerdPack
#   OR run: curl -L -o /usr/local/bin/jq https://github.com/stedolan/jq/releases/download/jq-1.6/jq-linux64 && chmod +x /usr/local/bin/jq
#
# Variables (can be overridden by environment variables):
JELLYFIN_URL="${JELLYFIN_URL:-http://localhost:8096}"  # Change this to your Jellyfin server URL
JELLYFIN_API_KEY="${JELLYFIN_API_KEY:-}"               # Your Jellyfin API key
JELLYFIN_USER_IDS="${USER_IDS:-}"                      # Jellyfin user ID(s) - space-separated for multiple users
CACHE_THRESHOLD="${CACHE_THRESHOLD:-90}"              # Percentage of cache usage that triggers moving files
CACHE_DRIVE="${CACHE_DRIVE:-/mnt/cache}"
DEBUG="${DEBUG:-true}"                                 # Set to true to enable debug logging

#########################################
##       Media Pool Configuration      ##
#########################################
#
# Configure your media pool paths. These are used to determine how files
# are handled when moving (movies move entire folder, TV moves by episode).
#
# Set these to match your Unraid share names:
MOVIES_POOL="${MOVIES_POOL:-movies-pool}"   # Your movies share name (e.g., "movies", "films", "movies-pool")
TV_POOL="${TV_POOL:-tv-pool}"               # Your TV shows share name (e.g., "tv", "shows", "tv-pool")

#########################################
##       Path Mapping Configuration    ##
#########################################
#
# Jellyfin often runs in a container with different mount paths than the host.
# Configure these to translate Jellyfin paths to local Unraid paths.
#
# Example: If Jellyfin sees files at /media/media/movies-pool/...
#          but Unraid has them at /mnt/cache/media/movies-pool/...
#          Set: JELLYFIN_PATH_PREFIX="/media/media"
#               LOCAL_PATH_PREFIX="/mnt/cache/media"
#
JELLYFIN_PATH_PREFIX="${JELLYFIN_PATH_PREFIX:-/media/media}"   # Path prefix as seen by Jellyfin
LOCAL_PATH_PREFIX="${LOCAL_PATH_PREFIX:-/mnt/cache/media}"    # Corresponding path on Unraid

#########################################
##       ARRAY_PATH Configuration      ##
#########################################
#
# Choose where files should be moved when clearing cache. Three options:
#
# OPTION 1: Direct Disk Path (Default - Recommended for most users)
#   ARRAY_PATH="/mnt/disk1"
#   - Files are written directly to a specific disk
#   - Guarantees files go to that exact disk
#   - Use /mnt/disk2, /mnt/disk3, etc. for other disks
#   - Best for: Users who want predictable, controlled file placement
#
# OPTION 2: User Share with Cache Bypass (Requires Unraid 6.9+)
#   ARRAY_PATH="/mnt/user0"
#   - Files go to array via user share, bypassing cache
#   - Unraid distributes files across disks based on allocation method
#   - Respects split levels and allocation settings
#   - Best for: Users who want Unraid to manage disk distribution
#
# OPTION 3: Standard User Share - DO NOT USE!
#   ARRAY_PATH="/mnt/user"   # WARNING: Can write back to cache!
#   - This path includes the cache drive
#   - Files may be written back to cache, defeating the purpose
#   - Only use if you understand the implications
#
ARRAY_PATH="${ARRAY_PATH:-/mnt/disk1}"

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/jellyfin_smart_mover.log"

# Dry-run mode flag (can be set via environment variable)
DRY_RUN="${DRY_RUN:-false}"

# Subtitle file extensions
SUBTITLE_EXTENSIONS="srt sub ass ssa vtt idx smi"

# Counters for summary statistics (reset in process_played_items)
STATS_MOVIES_COUNT=0        # Number of movies processed
STATS_MOVIES_VIDEOS=0       # Video files moved for movies
STATS_MOVIES_SUBTITLES=0    # Subtitle files moved for movies
STATS_TV_COUNT=0            # Number of TV episodes processed
STATS_TV_VIDEOS=0           # Video files moved for TV
STATS_TV_SUBTITLES=0        # Subtitle files moved for TV
STATS_SKIPPED=0             # Items skipped (not on cache/already exists)
STATS_ERRORS=0              # Errors encountered

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run|-n)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run, -n    Run without making any filesystem changes"
            echo "  --help, -h       Show this help message"
            exit 0
            ;;
        *)
            # Ignore unknown options for compatibility with Unraid User Scripts
            shift
            ;;
    esac
done

# Function to log messages to both console and file
log_message() {
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local message="[$timestamp] $1"
    echo "$message" | tee -a "$LOG_FILE"
}

# Function to emit status updates for the web UI
# These are parsed by the Python runner to show current progress
emit_status() {
    echo "STATUS: $1"
}

# Function to log to stderr (for use inside functions with redirected stdout)
# Only logs if DEBUG=true
log_stderr() {
    if [ "$DEBUG" = "true" ]; then
        local timestamp
        timestamp=$(date '+%Y-%m-%d %H:%M:%S')
        local message="[$timestamp] $1"
        echo "$message" >> "$LOG_FILE"
        echo "$message" >&2
    fi
}

# Initialize log file
initialize_logging() {
    # Create log file if it doesn't exist
    if [ ! -f "$LOG_FILE" ]; then
        touch "$LOG_FILE"
    fi

    # Add script start marker to log
    log_message "=== Smart Mover v$SCRIPT_VERSION started at $(date '+%Y-%m-%d %H:%M:%S') ==="
    log_message "Using log file: $LOG_FILE"
}

# Function to log debug messages (only when DEBUG=true)
debug_log() {
    if [ "$DEBUG" = "true" ]; then
        debug_log " $1"
    fi
}

# Function to log error messages
error_log() {
    log_message "ERROR: $1"
}

# Function to log dry-run actions
dry_run_log() {
    if [ "$DRY_RUN" = true ]; then
        log_message "[DRY-RUN] $1"
    fi
}

# Function to check if file has a subtitle extension
is_subtitle_file() {
    local file="$1"
    local ext="${file##*.}"
    ext=$(echo "$ext" | tr '[:upper:]' '[:lower:]')

    for sub_ext in $SUBTITLE_EXTENSIONS; do
        if [ "$ext" = "$sub_ext" ]; then
            return 0
        fi
    done
    return 1
}

# Function to detect media type based on path
# Returns: "movie" for movies-pool, "tv" for tv-pool, "unknown" otherwise
get_media_type() {
    local path="$1"

    if [[ "$path" == *"/$MOVIES_POOL/"* ]]; then
        echo "movie"
    elif [[ "$path" == *"/$TV_POOL/"* ]]; then
        echo "tv"
    else
        echo "unknown"
    fi
}

# Function to translate Jellyfin paths to local Unraid paths
# Jellyfin containers often mount media at different paths than the host
translate_jellyfin_path() {
    local jellyfin_path="$1"

    # Replace Jellyfin path prefix with local path prefix
    if [[ "$jellyfin_path" == "$JELLYFIN_PATH_PREFIX"* ]]; then
        echo "${jellyfin_path/$JELLYFIN_PATH_PREFIX/$LOCAL_PATH_PREFIX}"
    else
        # Path doesn't match expected prefix, return as-is
        echo "$jellyfin_path"
    fi
}

# Function to extract S##E## pattern from filename
# Returns the pattern (e.g., "S01E03") or empty string if not found
extract_episode_pattern() {
    local filename="$1"

    # Match S##E## pattern (case insensitive)
    if [[ "$filename" =~ [Ss]([0-9]{1,2})[Ee]([0-9]{1,2}) ]]; then
        # Return uppercase normalized format
        printf "S%02dE%02d" "$((10#${BASH_REMATCH[1]}))" "$((10#${BASH_REMATCH[2]}))"
    fi
}

# Function to move a single file (used by both movie and TV handlers)
# Uses rsync for safe cross-filesystem transfers with verification
# Returns 0 on success, 1 on failure, 2 on skip (already exists)
move_single_file() {
    local source_path="$1"
    local target_path="$2"
    local file_type="$3"  # For logging: "video", "subtitle", "file"

    # Check if target already exists
    if [ -f "$target_path" ]; then
        debug_log " Target $file_type already exists: $target_path"
        return 2  # Skip - already exists
    fi

    # Create target directory if needed
    local target_dir
    target_dir=$(dirname "$target_path")

    if [ "$DRY_RUN" = true ]; then
        if [ ! -d "$target_dir" ]; then
            dry_run_log "Would create directory: $target_dir"
        fi
        local file_size
        file_size=$(du -h "$source_path" 2>/dev/null | cut -f1)
        dry_run_log "Would move $file_type: $source_path ($file_size) -> $target_path"
        return 0
    else
        if ! mkdir -p "$target_dir"; then
            log_message "ERROR: Failed to create target directory: $target_dir"
            return 1
        fi

        # Use rsync for safe transfer: preserves attributes (including xattrs), verifies transfer, only removes source on success
        if rsync -aX --remove-source-files "$source_path" "$target_path"; then
            log_message "Successfully moved $file_type: $source_path"
            return 0
        else
            log_message "ERROR: Failed to move $file_type: $source_path"
            return 1
        fi
    fi
}

# Function to clean up empty directories after moving files
# Walks up from the given path, removing empty directories until it hits the stop path
cleanup_empty_dirs() {
    local start_path="$1"
    local stop_path="$2"  # Don't delete this directory or anything above it

    local current_dir="$start_path"

    while [ "$current_dir" != "$stop_path" ] && [ "$current_dir" != "/" ]; do
        # Only attempt removal if directory exists and is empty
        if [ -d "$current_dir" ] && [ -z "$(ls -A "$current_dir" 2>/dev/null)" ]; then
            if [ "$DRY_RUN" = true ]; then
                dry_run_log "Would remove empty directory: $current_dir"
            else
                if rmdir "$current_dir" 2>/dev/null; then
                    debug_log " Removed empty directory: $current_dir"
                else
                    # Directory not empty or permission denied, stop here
                    break
                fi
            fi
        else
            # Directory not empty, stop climbing
            break
        fi

        # Move up to parent directory
        current_dir=$(dirname "$current_dir")
    done
}

# Function to move associated subtitle files for TV episodes
# Finds files in the same directory matching the S##E## pattern
# Updates global STATS_TV_SUBTITLES counter
move_tv_subtitles() {
    local video_path="$1"
    local video_dir
    video_dir=$(dirname "$video_path")
    local video_filename
    video_filename=$(basename "$video_path")

    # Extract episode pattern from video filename
    local episode_pattern
    episode_pattern=$(extract_episode_pattern "$video_filename")

    if [ -z "$episode_pattern" ]; then
        debug_log " No episode pattern found in $video_filename, skipping subtitle search"
        return 0
    fi

    debug_log " Looking for subtitles matching pattern $episode_pattern in $video_dir"

    local subtitle_count=0

    # Find all files in the same directory
    for file in "$video_dir"/*; do
        [ -f "$file" ] || continue

        local filename
        filename=$(basename "$file")

        # Skip the video file itself
        [ "$filename" = "$video_filename" ] && continue

        # Check if it's a subtitle file
        if ! is_subtitle_file "$filename"; then
            continue
        fi

        # Check if it matches the episode pattern
        local file_pattern
        file_pattern=$(extract_episode_pattern "$filename")

        if [ "$file_pattern" = "$episode_pattern" ]; then
            debug_log " Found matching subtitle: $filename"

            # Calculate target path
            local rel_path="${file#$CACHE_DRIVE/}"
            local target_path="$ARRAY_PATH/$rel_path"

            local move_result
            move_single_file "$file" "$target_path" "subtitle"
            move_result=$?

            if [ "$move_result" -eq 0 ]; then
                subtitle_count=$((subtitle_count + 1))
            fi
        fi
    done

    if [ "$subtitle_count" -gt 0 ]; then
        # Update global stats
        STATS_TV_SUBTITLES=$((STATS_TV_SUBTITLES + subtitle_count))

        if [ "$DRY_RUN" = true ]; then
            debug_log " Would move $subtitle_count subtitle file(s) for $episode_pattern"
        else
            debug_log " Moved $subtitle_count subtitle file(s) for $episode_pattern"
        fi
    fi

    return 0
}

# Function to move entire movie folder
# Returns 0 on success (files moved), 1 on error, 2 if all files already existed
# Updates global STATS_MOVIES_* counters
move_movie_folder() {
    local video_path="$1"
    local movie_dir
    movie_dir=$(dirname "$video_path")

    debug_log " Moving entire movie folder: $movie_dir"

    local file_count=0
    local video_count=0
    local subtitle_count=0
    local skip_count=0
    local error_count=0

    # Move all files in the movie directory
    for file in "$movie_dir"/*; do
        [ -f "$file" ] || continue

        local filename
        filename=$(basename "$file")

        # Calculate target path
        local rel_path="${file#$CACHE_DRIVE/}"
        local target_path="$ARRAY_PATH/$rel_path"

        # Determine file type for logging and counting
        local file_type="file"
        local is_subtitle=false
        if is_subtitle_file "$filename"; then
            file_type="subtitle"
            is_subtitle=true
        elif [[ "$file" = "$video_path" ]]; then
            file_type="video"
        fi

        local move_result
        move_single_file "$file" "$target_path" "$file_type"
        move_result=$?

        case $move_result in
            0)
                file_count=$((file_count + 1))
                if [ "$is_subtitle" = true ]; then
                    subtitle_count=$((subtitle_count + 1))
                else
                    video_count=$((video_count + 1))
                fi
                ;;
            1) error_count=$((error_count + 1)) ;;
            2) skip_count=$((skip_count + 1)) ;;
        esac
    done

    if [ "$DRY_RUN" = true ]; then
        debug_log " Would move $file_count file(s) from movie folder ($video_count video, $subtitle_count subtitles)"
    else
        debug_log " Moved $file_count file(s) from movie folder ($video_count video, $subtitle_count subtitles)"
    fi

    # Update global stats if we moved files
    if [ "$file_count" -gt 0 ]; then
        STATS_MOVIES_COUNT=$((STATS_MOVIES_COUNT + 1))
        STATS_MOVIES_VIDEOS=$((STATS_MOVIES_VIDEOS + video_count))
        STATS_MOVIES_SUBTITLES=$((STATS_MOVIES_SUBTITLES + subtitle_count))
    fi

    # Clean up empty movie directory after moving files
    # cleanup_empty_dirs handles dry-run mode internally
    if [ "$file_count" -gt 0 ] || [ "$DRY_RUN" = true ]; then
        cleanup_empty_dirs "$movie_dir" "$CACHE_DRIVE"
    fi

    # Return appropriate status
    if [ "$error_count" -gt 0 ]; then
        STATS_ERRORS=$((STATS_ERRORS + error_count))
        return 1
    elif [ "$file_count" -gt 0 ]; then
        return 0
    else
        return 2  # All files already existed
    fi
}

# Function to validate API key format
# Jellyfin API keys are 32-character hexadecimal strings
validate_api_key_format() {
    local api_key="$1"

    # Check if empty
    if [ -z "$api_key" ]; then
        log_message "ERROR: JELLYFIN_API_KEY is empty"
        log_message "ERROR: Please set your Jellyfin API key in the script configuration"
        log_message "ERROR: You can generate an API key in Jellyfin: Dashboard > API Keys > Add"
        return 1
    fi

    # Check length (should be 32 characters)
    local key_length=${#api_key}
    if [ "$key_length" -ne 32 ]; then
        log_message "ERROR: Invalid API key format - expected 32 characters, got $key_length"
        log_message "ERROR: Jellyfin API keys should be exactly 32 hexadecimal characters"
        log_message "ERROR: Example format: 0123456789abcdef0123456789abcdef"
        return 1
    fi

    # Check if it's a valid hexadecimal string (only 0-9, a-f, A-F)
    if ! [[ "$api_key" =~ ^[0-9a-fA-F]{32}$ ]]; then
        log_message "ERROR: Invalid API key format - must contain only hexadecimal characters (0-9, a-f)"
        log_message "ERROR: Your API key contains invalid characters"
        log_message "ERROR: Please verify your API key in Jellyfin: Dashboard > API Keys"
        return 1
    fi

    debug_log " API key format validated successfully"
    return 0
}

# Function to validate a single User ID format
# Jellyfin User IDs are UUIDs (with or without dashes)
validate_single_user_id() {
    local user_id="$1"

    # Remove dashes for validation
    local user_id_no_dashes="${user_id//-/}"

    # Check length (should be 32 characters without dashes)
    local id_length=${#user_id_no_dashes}
    if [ "$id_length" -ne 32 ]; then
        log_message "ERROR: Invalid User ID format for '$user_id' - expected 32 hexadecimal characters"
        return 1
    fi

    # Check if it's a valid hexadecimal string
    if ! [[ "$user_id_no_dashes" =~ ^[0-9a-fA-F]{32}$ ]]; then
        log_message "ERROR: Invalid User ID format for '$user_id' - must contain only hexadecimal characters"
        return 1
    fi

    return 0
}

# Function to validate User IDs (supports multiple space-separated IDs)
validate_user_ids_format() {
    # Check if empty
    if [ -z "$JELLYFIN_USER_IDS" ]; then
        log_message "ERROR: JELLYFIN_USER_IDS is empty"
        log_message "ERROR: Please set your Jellyfin user ID(s) in the script configuration"
        log_message "ERROR: For multiple users, separate IDs with spaces"
        log_message "ERROR: You can find user IDs in Jellyfin: Dashboard > Users > Click user > URL contains the ID"
        return 1
    fi

    local valid_count=0
    for user_id in $JELLYFIN_USER_IDS; do
        if validate_single_user_id "$user_id"; then
            valid_count=$((valid_count + 1))
        else
            return 1
        fi
    done

    if [ "$valid_count" -eq 1 ]; then
        debug_log " 1 user ID validated successfully"
    else
        debug_log " $valid_count user IDs validated successfully"
    fi
    return 0
}

# Function to test API endpoints
test_api_endpoints() {
    debug_log " Testing API connection..."

    # Test base URL
    local test_url="$JELLYFIN_URL/System/Info/Public"
    debug_log " Testing base URL: $test_url"

    local tmp_response
    tmp_response=$(mktemp)
    local tmp_headers
    tmp_headers=$(mktemp)

    # Test with simple GET request
    if ! curl -s -f -o "$tmp_response" -D "$tmp_headers" \
        -H "X-MediaBrowser-Token: $JELLYFIN_API_KEY" \
        -H "Accept: application/json" \
        "$test_url"; then
        log_message "ERROR: Failed to connect to Jellyfin server at $JELLYFIN_URL"
        rm -f "$tmp_response" "$tmp_headers"
        return 1
    fi

    # Get HTTP status code
    local status_code
    status_code=$(grep -i "^HTTP" "$tmp_headers" | tail -n1 | awk '{print $2}')

    if [ "$status_code" != "200" ]; then
        log_message "ERROR: Server returned status code $status_code"
        rm -f "$tmp_response" "$tmp_headers"
        return 1
    fi

    # Test user endpoint
    local user_url="$JELLYFIN_URL/Users/$JELLYFIN_USER_ID"
    debug_log " Testing user endpoint: $user_url"

    if ! curl -s -f -o "$tmp_response" -D "$tmp_headers" \
        -H "X-MediaBrowser-Token: $JELLYFIN_API_KEY" \
        -H "Accept: application/json" \
        "$user_url"; then
        log_message "ERROR: Failed to access user endpoint. Check JELLYFIN_USER_ID"
        rm -f "$tmp_response" "$tmp_headers"
        return 1
    fi

    # Get HTTP status code for user endpoint
    status_code=$(grep -i "^HTTP" "$tmp_headers" | tail -n1 | awk '{print $2}')

    if [ "$status_code" != "200" ]; then
        log_message "ERROR: User endpoint returned status code $status_code"
        rm -f "$tmp_response" "$tmp_headers"
        return 1
    fi

    # Test items endpoint with minimal query
    local items_url="$JELLYFIN_URL/Users/$JELLYFIN_USER_ID/Items?Limit=1"
    debug_log " Testing items endpoint: $items_url"

    if ! curl -s -f -o "$tmp_response" -D "$tmp_headers" \
        -H "X-MediaBrowser-Token: $JELLYFIN_API_KEY" \
        -H "Accept: application/json" \
        "$items_url"; then
        log_message "ERROR: Failed to access items endpoint"
        rm -f "$tmp_response" "$tmp_headers"
        return 1
    fi

    # Validate JSON response
    if ! jq empty "$tmp_response" > /dev/null 2>&1; then
        log_message "ERROR: Invalid JSON response from items endpoint"
        debug_log " Raw response: $(cat "$tmp_response")"
        rm -f "$tmp_response" "$tmp_headers"
        return 1
    fi

    debug_log " All API endpoints tested successfully"
    rm -f "$tmp_response" "$tmp_headers"
    return 0
}

# Function to make API call with logging
make_api_call() {
    local url="$1"
    local method="$2"
    local description="$3"

    log_stderr "DEBUG: Making $method request to: $url at $(date '+%Y-%m-%d %H:%M:%S')"
    log_stderr "DEBUG: Request headers: X-MediaBrowser-Token: [hidden], Accept: application/json"

    # Create temporary files
    local tmp_response
    tmp_response=$(mktemp)
    local tmp_final
    tmp_final=$(mktemp)
    local tmp_headers
    tmp_headers=$(mktemp)

    # Ensure temp files are cleaned up
    trap 'rm -f "$tmp_response" "$tmp_final" "$tmp_headers"' EXIT

    # Make the curl call with verbose output for debugging
    if ! curl -v -s -w "\n%{http_code}" \
        -X "$method" \
        -H "X-MediaBrowser-Token: $JELLYFIN_API_KEY" \
        -H "Accept: application/json" \
        "$url" 2>"$tmp_headers" > "$tmp_response"; then
        log_stderr "ERROR: Curl command failed for $description"
        log_stderr "DEBUG: Curl headers: $(cat "$tmp_headers")"
        return 1
    fi

    # Extract status code from last line and remove it from response
    local status_code
    status_code=$(tail -n1 "$tmp_response")
    head -n -1 "$tmp_response" > "$tmp_final"

    log_stderr "DEBUG: API response code for $description: $status_code"
    log_stderr "DEBUG: Curl headers: $(cat "$tmp_headers")"

    # Log response size and preview for debugging
    local response_size
    response_size=$(wc -c < "$tmp_final")
    log_stderr "DEBUG: Response size: $response_size bytes"

    # Only show preview in debug, full response is passed through
    if [ "$response_size" -lt 2000 ]; then
        log_stderr "DEBUG: Full response: $(cat "$tmp_final")"
    else
        local response_preview
        response_preview=$(head -c 1000 "$tmp_final")
        log_stderr "DEBUG: First 1000 chars of response: $response_preview..."
    fi

    if [ "$status_code" != "200" ]; then
        log_stderr "ERROR: API call failed for $description. Status code: $status_code"
        log_stderr "DEBUG: Full response body: $(cat "$tmp_final")"
        return 1
    fi

    cat "$tmp_final"
    return 0
}

# Function to get played items from Jellyfin for a single user
# Outputs tab-separated: Name\tType\tPath
get_played_items_for_user() {
    local user_id="$1"

    log_stderr "DEBUG: Fetching played items for user $user_id"

    # Create temporary files
    local tmp_response
    tmp_response=$(mktemp)
    local tmp_items
    tmp_items=$(mktemp)
    local tmp_error
    tmp_error=$(mktemp)

    # Get the API response
    local api_url="$JELLYFIN_URL/Users/$user_id/Items"
    local query_params="IsPlayed=true&IncludeItemTypes=Movie,Episode&SortBy=LastPlayedDate&SortOrder=Descending&Recursive=true&Fields=Path,SeriesName"
    local full_url="${api_url}?${query_params}"

    # Make the API call and save to temp file
    log_stderr "DEBUG: Making API call to get played items..."
    if ! make_api_call "$full_url" "GET" "Getting played items for user $user_id" > "$tmp_response"; then
        log_stderr "ERROR: API call failed for user $user_id"
        rm -f "$tmp_response" "$tmp_items" "$tmp_error"
        return 1
    fi
    log_stderr "DEBUG: API call completed successfully"

    # Verify we got a response
    local response_size
    response_size=$(wc -c < "$tmp_response")
    log_stderr "DEBUG: Response file size: $response_size bytes"

    if [ ! -s "$tmp_response" ]; then
        log_stderr "DEBUG: Empty response from API for user $user_id"
        rm -f "$tmp_response" "$tmp_items" "$tmp_error"
        return 0
    fi

    # Log raw response item count for debugging
    log_stderr "DEBUG: Parsing JSON response..."
    local total_items
    total_items=$(jq '.TotalRecordCount // 0' "$tmp_response" 2>/dev/null)
    log_stderr "DEBUG: Jellyfin returned TotalRecordCount: $total_items for user $user_id"

    # Also log the number of items in the Items array
    local items_array_count
    items_array_count=$(jq '.Items | length' "$tmp_response" 2>/dev/null)
    log_stderr "DEBUG: Items array contains: $items_array_count items"

    # Process the response with jq - extract Name, Type, SeriesName (for episodes), and Path
    # Format: Name|Type|SeriesName|Path (using | as delimiter since names can have tabs)
    log_stderr "DEBUG: Extracting item details with jq..."
    local jq_cmd='.Items[] | select(.Path) | [.Name, .Type, (.SeriesName // ""), .Path] | join("|")'
    if ! jq -r "$jq_cmd" "$tmp_response" > "$tmp_items" 2> "$tmp_error"; then
        log_stderr "ERROR: Failed to parse played items JSON for user $user_id"
        log_stderr "DEBUG: JQ Error: $(cat "$tmp_error")"
        rm -f "$tmp_response" "$tmp_items" "$tmp_error"
        return 1
    fi
    log_stderr "DEBUG: JQ extraction completed"

    # Output the items (if any)
    if [ -s "$tmp_items" ]; then
        local count
        count=$(wc -l < "$tmp_items")
        log_stderr "DEBUG: Found $count played items with valid paths for user $user_id"

        # Log first few items for debugging
        log_stderr "DEBUG: First 5 items:"
        head -5 "$tmp_items" | while IFS='|' read -r name type series path; do
            if [ "$type" = "Episode" ] && [ -n "$series" ]; then
                log_stderr "DEBUG:   - [TV] $series - $name"
            else
                log_stderr "DEBUG:   - [$type] $name"
            fi
        done

        cat "$tmp_items"
    else
        log_stderr "DEBUG: No items with valid paths found for user $user_id"
    fi

    rm -f "$tmp_response" "$tmp_items" "$tmp_error"
    return 0
}

# Function to get played items from Jellyfin (all configured users)
# Outputs: Name|Type|SeriesName|Path (one per line, deduplicated by path)
get_played_items() {
    log_stderr "DEBUG: Starting get_played_items function at $(date '+%Y-%m-%d %H:%M:%S')"

    # Create temporary file for combined results
    local tmp_all_items
    tmp_all_items=$(mktemp)

    # Ensure temp file is cleaned up
    trap 'rm -f "$tmp_all_items"' EXIT

    local user_count=0
    for user_id in $JELLYFIN_USER_IDS; do
        user_count=$((user_count + 1))
        get_played_items_for_user "$user_id" >> "$tmp_all_items"
    done

    if [ "$user_count" -gt 1 ]; then
        log_stderr "DEBUG: Queried $user_count users for played items"
    fi

    # Remove duplicates based on path (4th field) while keeping full item info
    local tmp_unique
    tmp_unique=$(mktemp)
    # Sort by path (field 4), then keep only first occurrence of each path
    sort -t'|' -k4,4 -u "$tmp_all_items" > "$tmp_unique"

    # Handle empty results
    if [ ! -s "$tmp_unique" ]; then
        log_stderr "DEBUG: No played items found across all users"
        rm -f "$tmp_unique"
        return 0
    fi

    # Log total unique items
    local total_count
    total_count=$(wc -l < "$tmp_unique")
    log_stderr "DEBUG: Found $total_count unique played items across $user_count user(s)"

    # Output the unique items
    cat "$tmp_unique"
    rm -f "$tmp_unique"
    return 0
}

# Function to process a single item
# Returns 0 on success (file moved), 1 on error, 2 on skip (not found, not on cache, already exists)
process_item() {
    local jellyfin_path="$1"
    local cache_usage="$2"

    # Skip empty paths or debug messages
    if [ -z "$jellyfin_path" ] || [[ "$jellyfin_path" == *"DEBUG:"* ]] || [[ "$jellyfin_path" == *"ERROR:"* ]]; then
        return 2  # Skip
    fi

    # Translate Jellyfin path to local Unraid path
    local item_path
    item_path=$(translate_jellyfin_path "$jellyfin_path")

    debug_log " Processing item: $jellyfin_path"
    debug_log " Translated path: $item_path"

    # Check if file exists
    if [ ! -f "$item_path" ]; then
        debug_log " Skipping $item_path - file not found (not on cache)"
        return 2  # Skip - file not on cache
    fi

    # Check if file is on cache drive
    if [[ "$item_path" != "$CACHE_DRIVE"* ]]; then
        debug_log " Skipping $item_path - not on cache drive"
        return 2  # Skip - not on cache
    fi

    # Detect media type and handle accordingly
    local media_type
    media_type=$(get_media_type "$item_path")
    debug_log " Detected media type: $media_type"

    case "$media_type" in
        movie)
            # For movies, move the entire folder
            debug_log " Processing as movie - will move entire folder"
            move_movie_folder "$item_path"
            return $?
            ;;
        tv)
            # For TV, move the video file then find and move matching subtitles
            debug_log " Processing as TV episode - will move video and matching subtitles"

            # Get target path on array for the video
            local rel_path="${item_path#$CACHE_DRIVE/}"
            local array_path="$ARRAY_PATH/$rel_path"
            local item_dir
            item_dir=$(dirname "$item_path")

            # Check if target already exists
            if [ -f "$array_path" ]; then
                debug_log " Target video already exists: $array_path"
                # Still check for subtitles that might need moving
                move_tv_subtitles "$item_path"
                return 2  # Skip - already exists
            fi

            # Move the video file
            local move_result
            move_single_file "$item_path" "$array_path" "video"
            move_result=$?

            if [ "$move_result" -eq 1 ]; then
                STATS_ERRORS=$((STATS_ERRORS + 1))
                return 1  # Error
            fi

            # Successfully moved video - update stats
            if [ "$move_result" -eq 0 ]; then
                STATS_TV_COUNT=$((STATS_TV_COUNT + 1))
                STATS_TV_VIDEOS=$((STATS_TV_VIDEOS + 1))
            fi

            # Move associated subtitle files (updates STATS_TV_SUBTITLES internally)
            move_tv_subtitles "$item_path"

            # Clean up empty directories (season folder, show folder)
            # cleanup_empty_dirs handles dry-run mode internally
            cleanup_empty_dirs "$item_dir" "$CACHE_DRIVE"

            return $move_result
            ;;
        *)
            # Unknown media type - use legacy behavior (just move the file)
            debug_log " Unknown media type - moving single file only"

            local rel_path="${item_path#$CACHE_DRIVE/}"
            local array_path="$ARRAY_PATH/$rel_path"
            local item_dir
            item_dir=$(dirname "$item_path")

            # Check if target already exists
            if [ -f "$array_path" ]; then
                debug_log " Target file already exists: $array_path"
                return 2  # Skip - already exists
            fi

            local move_result
            move_single_file "$item_path" "$array_path" "video"
            move_result=$?

            # Clean up empty directories (cleanup_empty_dirs handles dry-run internally)
            if [ "$move_result" -eq 0 ]; then
                cleanup_empty_dirs "$item_dir" "$CACHE_DRIVE"
            fi

            return $move_result
            ;;
    esac
}

# Function to check if an item needs to be moved (is on cache and not already on array)
# Returns 0 if item needs moving, 1 otherwise
item_needs_moving() {
    local jellyfin_path="$1"

    # Translate Jellyfin path to local Unraid path
    local item_path
    item_path=$(translate_jellyfin_path "$jellyfin_path")

    # Check if file exists on cache
    if [ ! -f "$item_path" ]; then
        return 1  # File not found (not on cache)
    fi

    # Check if file is on cache drive
    if [[ "$item_path" != "$CACHE_DRIVE"* ]]; then
        return 1  # Not on cache drive
    fi

    # Check if already exists on array
    local rel_path="${item_path#$CACHE_DRIVE/}"
    local array_path="$ARRAY_PATH/$rel_path"

    if [ -f "$array_path" ]; then
        return 1  # Already exists on array
    fi

    return 0  # Needs moving
}

# Function to process all played items
process_played_items() {
    local cache_usage=$1
    local count=0
    local skipped=0

    # Reset global statistics counters
    STATS_MOVIES_COUNT=0
    STATS_MOVIES_VIDEOS=0
    STATS_MOVIES_SUBTITLES=0
    STATS_TV_COUNT=0
    STATS_TV_VIDEOS=0
    STATS_TV_SUBTITLES=0
    STATS_SKIPPED=0
    STATS_ERRORS=0

    debug_log "Processing played items with cache usage at $cache_usage%"

    # Create temporary files for played items
    local tmp_items
    tmp_items=$(mktemp)
    local tmp_to_move
    tmp_to_move=$(mktemp)

    # Ensure temp files are cleaned up
    trap 'rm -f "$tmp_items" "$tmp_to_move"' EXIT

    log_message "Fetching played items from Jellyfin..."

    # Get list of played items and save to temp file
    if ! get_played_items > "$tmp_items"; then
        log_message "ERROR: Failed to get played items list"
        return 1
    fi

    # If no items found, exit successfully
    if [ ! -s "$tmp_items" ]; then
        log_message "No played items found in Jellyfin"
        return 0
    fi

    # Count total items from Jellyfin
    local total_jellyfin
    total_jellyfin=$(wc -l < "$tmp_items")

    log_message "Scanning $total_jellyfin played items for files on cache..."

    # Pre-scan: filter to only items that need moving

    while IFS='|' read -r name type series_name path; do
        # Skip empty lines and debug/error messages
        if [ -z "$path" ] || [[ "$path" == *"DEBUG:"* ]] || [[ "$path" == *"ERROR:"* ]]; then
            continue
        fi

        if item_needs_moving "$path"; then
            echo "$name|$type|$series_name|$path" >> "$tmp_to_move"
        fi
    done < "$tmp_items"

    # Check if any items need moving
    if [ ! -s "$tmp_to_move" ]; then
        log_message "========================================="
        log_message "No items need moving"
        log_message "========================================="
        log_message "  Checked $total_jellyfin played items from Jellyfin"
        log_message "  All items are either already on array or not on cache"
        return 0
    fi

    # Count items to move
    local total_to_move
    total_to_move=$(wc -l < "$tmp_to_move")

    # Display list of items that WILL be moved
    log_message "========================================="
    log_message "Items to move ($total_to_move of $total_jellyfin played):"
    log_message "========================================="

    local item_num=0
    while IFS='|' read -r name type series_name path; do
        item_num=$((item_num + 1))

        # Format display based on type
        if [ "$type" = "Episode" ] && [ -n "$series_name" ]; then
            log_message "  $item_num. [TV] $series_name - $name"
        elif [ "$type" = "Movie" ]; then
            log_message "  $item_num. [Movie] $name"
        else
            log_message "  $item_num. [$type] $name"
        fi

        # Show translated local path
        local local_path
        local_path=$(translate_jellyfin_path "$path")
        log_message "      Cache: $local_path"
    done < "$tmp_to_move"

    log_message "========================================="

    # Process each item that needs moving
    while IFS='|' read -r name type series_name path; do
        count=$((count + 1))

        # Show progress for each item
        if [ "$DRY_RUN" = true ]; then
            log_message "[$count/$total_to_move] Would move: $name"
            emit_status "[$count/$total_to_move] Checking: $name"
        else
            log_message "[$count/$total_to_move] Moving: $name"
            emit_status "[$count/$total_to_move] Moving: $name"
        fi

        local result
        process_item "$path" "$cache_usage"
        result=$?

        # Track skipped items (return code 2)
        if [ "$result" -eq 2 ]; then
            skipped=$((skipped + 1))
        fi
    done < "$tmp_to_move"

    # Calculate totals
    local total_moved=$((STATS_MOVIES_COUNT + STATS_TV_COUNT))
    local total_videos=$((STATS_MOVIES_VIDEOS + STATS_TV_VIDEOS))
    local total_subtitles=$((STATS_MOVIES_SUBTITLES + STATS_TV_SUBTITLES))
    local total_files=$((total_videos + total_subtitles))

    # Display summary
    if [ "$DRY_RUN" = true ]; then
        log_message "========================================="
        log_message "Dry-run summary: Processed $count played items from Jellyfin"
        log_message "========================================="
        if [ "$STATS_MOVIES_COUNT" -gt 0 ]; then
            log_message "  Movies: $STATS_MOVIES_COUNT would be moved"
            log_message "    - Video files: $STATS_MOVIES_VIDEOS"
            log_message "    - Subtitle files: $STATS_MOVIES_SUBTITLES"
        fi
        if [ "$STATS_TV_COUNT" -gt 0 ]; then
            log_message "  TV Episodes: $STATS_TV_COUNT would be moved"
            log_message "    - Video files: $STATS_TV_VIDEOS"
            log_message "    - Subtitle files: $STATS_TV_SUBTITLES"
        fi
        if [ "$total_moved" -gt 0 ]; then
            log_message "  -----------------------------------------"
            log_message "  Total: $total_files files ($total_videos video, $total_subtitles subtitles)"
        else
            log_message "  No files to move (all on array or not found)"
        fi
        log_message "  Skipped: $skipped items (not on cache or already on array)"
        if [ "$STATS_ERRORS" -gt 0 ]; then
            log_message "  Errors: $STATS_ERRORS"
        fi
    else
        log_message "========================================="
        log_message "Summary: Processed $count played items from Jellyfin"
        log_message "========================================="
        if [ "$STATS_MOVIES_COUNT" -gt 0 ]; then
            log_message "  Movies: $STATS_MOVIES_COUNT moved"
            log_message "    - Video files: $STATS_MOVIES_VIDEOS"
            log_message "    - Subtitle files: $STATS_MOVIES_SUBTITLES"
        fi
        if [ "$STATS_TV_COUNT" -gt 0 ]; then
            log_message "  TV Episodes: $STATS_TV_COUNT moved"
            log_message "    - Video files: $STATS_TV_VIDEOS"
            log_message "    - Subtitle files: $STATS_TV_SUBTITLES"
        fi
        if [ "$total_moved" -gt 0 ]; then
            log_message "  -----------------------------------------"
            log_message "  Total: $total_files files ($total_videos video, $total_subtitles subtitles)"
        else
            log_message "  No files moved (all on array or not found)"
        fi
        log_message "  Skipped: $skipped items (not on cache or already on array)"
        if [ "$STATS_ERRORS" -gt 0 ]; then
            log_message "  Errors: $STATS_ERRORS"
        fi
    fi
    return 0
}

# Function to validate environment
validate_environment() {
    debug_log "Validating environment..."

    # Check required environment variables
    if [ -z "$JELLYFIN_URL" ]; then
        log_message "ERROR: JELLYFIN_URL is not set"
        return 1
    fi

    # Validate API key format before attempting any API calls
    if ! validate_api_key_format "$JELLYFIN_API_KEY"; then
        return 1
    fi

    # Validate User ID(s) format before attempting any API calls
    if ! validate_user_ids_format; then
        return 1
    fi

    # Test Jellyfin connection
    log_message "Connecting to Jellyfin at $JELLYFIN_URL..."
    local test_response
    test_response=$(make_api_call "$JELLYFIN_URL/System/Info" "GET" "System Info")
    if [ $? -ne 0 ]; then
        log_message "ERROR: Failed to connect to Jellyfin server"
        return 1
    fi

    # Extract server name for logging
    local server_name
    server_name=$(echo "$test_response" | jq -r '.ServerName // "unknown"' 2>/dev/null)
    log_message "Connected to Jellyfin server: $server_name"

    # Validate each user ID exists
    for user_id in $JELLYFIN_USER_IDS; do
        local user_test
        user_test=$(make_api_call "$JELLYFIN_URL/Users/$user_id" "GET" "User Info for $user_id")
        local api_result=$?
        if [ $api_result -ne 0 ]; then
            log_message "ERROR: Invalid user ID: $user_id"
            return 1
        fi
        # Extract username from response for logging
        local username
        username=$(echo "$user_test" | jq -r '.Name // "unknown"' 2>/dev/null)
        log_message "Monitoring played items for user: $username"
    done

    return 0
}

# Function to check and install jq if needed
check_jq() {
    if ! command -v jq &> /dev/null; then
        log_message "jq not found. Attempting to install..."
        if curl -L -o /usr/local/bin/jq https://github.com/stedolan/jq/releases/download/jq-1.6/jq-linux64; then
            chmod +x /usr/local/bin/jq
            log_message "jq installed successfully"
        else
            log_message "ERROR: Failed to install jq. Please install it manually through the NerdPack plugin"
            log_message "Or run: curl -L -o /usr/local/bin/jq https://github.com/stedolan/jq/releases/download/jq-1.6/jq-linux64 && chmod +x /usr/local/bin/jq"
            exit 1
        fi
    fi
}

# Function to check if mover is running
is_mover_running() {
    if [ -f /var/run/mover.pid ]; then
        if kill -0 $(cat /var/run/mover.pid) 2>/dev/null; then
            return 0  # Mover is running
        fi
    fi
    return 1  # Mover is not running
}

# Function to check if parity check is running
is_parity_running() {
    if [ -f /proc/mdstat ]; then
        if grep -q "resync" /proc/mdstat; then
            return 0  # Parity check is running
        fi
    fi
    return 1  # Parity check is not running
}

# Function to check cache usage
check_cache_usage() {
    local cache_path="$1"
    local usage

    # Get disk usage percentage without logging
    usage=$(df -h "$cache_path" | awk 'NR==2 {print $5}' | sed 's/%//')

    if [ -z "$usage" ]; then
        log_message "ERROR: Could not determine cache usage"
        return 1
    fi

    # Return just the number
    echo "$usage"
    return 0
}

# Main function
main() {
    # Initialize logging
    initialize_logging
    emit_status "Initializing..."

    # Announce dry-run mode if enabled
    if [ "$DRY_RUN" = true ]; then
        log_message "========================================="
        log_message "DRY-RUN MODE - No files will be moved"
        log_message "========================================="
    fi

    # Check for jq
    emit_status "Checking dependencies..."
    if ! check_jq; then
        log_message "Error: jq is required but not installed"
        exit 1
    fi

    # Validate environment first
    emit_status "Validating environment..."
    if ! validate_environment; then
        log_message "ERROR: Environment validation failed"
        exit 1
    fi

    # Validate required paths
    if [ ! -d "$CACHE_DRIVE" ]; then
        log_message "ERROR: Cache drive path does not exist: $CACHE_DRIVE"
        exit 1
    fi

    if [ ! -d "$ARRAY_PATH" ]; then
        log_message "ERROR: Array path does not exist: $ARRAY_PATH"
        exit 1
    fi

    # Check if mover is running
    if is_mover_running; then
        log_message "Unraid mover is currently running, skipping"
        emit_status "Skipped - Unraid mover is running"
        exit 0
    fi

    # Check cache usage
    emit_status "Checking cache usage..."
    local cache_usage
    cache_usage=$(check_cache_usage "$CACHE_DRIVE")
    if [ $? -ne 0 ]; then
        log_message "ERROR: Failed to check cache usage"
        exit 1
    fi
    log_message "Cache: ${cache_usage}% used (threshold: ${CACHE_THRESHOLD}%)"

    # Only process if cache usage is above threshold
    if [ "$cache_usage" -ge "$CACHE_THRESHOLD" ]; then
        emit_status "Fetching played items from Jellyfin..."
        if ! process_played_items "$cache_usage"; then
            log_message "ERROR: Failed to process played items"
            exit 1
        fi
    else
        log_message "Cache usage (${cache_usage}%) is below threshold (${CACHE_THRESHOLD}%), no action needed"
        emit_status "Complete - Cache below threshold"
    fi

    # Dry-run completion message
    if [ "$DRY_RUN" = true ]; then
        log_message "========================================="
        log_message "DRY-RUN COMPLETE"
        log_message "To actually move files, run without --dry-run"
        log_message "========================================="
        emit_status "Complete - Dry run finished"
    else
        emit_status "Complete"
    fi
}

# Run main function
main
