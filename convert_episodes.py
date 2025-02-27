import os
import re
import subprocess
import argparse
from pathlib import Path

def parse_arguments():
    parser = argparse.ArgumentParser(description="Convert video files to HEVC and AAC formats.")
    parser.add_argument("-limit", type=int, default=10, help="Limit the number of conversions.")
    parser.add_argument("-size", type=str, default="0", help="Size limit for conversions (e.g., 10G, 500M).")
    return parser.parse_args()

def convert_size_to_bytes(size_str):
    if size_str == "0":
        return 0
    units = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    unit = size_str[-1].upper()
    if unit in units:
        return int(size_str[:-1]) * units[unit]
    return int(size_str)

def process_video(input_file, size_limit_bytes, conversion_count):
    filename = Path(input_file).name
    dir_path = Path(input_file).parent

    # Skip files that are already in x265 or HEVC format
    if re.search(r'(x265|HEVC|h265|H265|X265|hevc)', filename, re.IGNORECASE):
        print(f"Skipping {filename} as it's already in x265/HEVC format.")
        return conversion_count, 0

    # Replace h264, x264, etc., in the filename for HEVC conversion and handle audio format changes
    output = re.sub(r'(h264|x264|H264|H\.264|h\.264|X264|xvid|XviD|divx|DivX)', 'HEVC', filename, flags=re.IGNORECASE)
    output = re.sub(r'(MP3|mp3|DTS|dts|WMA|wma|FLAC|flac)', 'AAC', output, flags=re.IGNORECASE)
    output_file = f"{Path(output).stem}.mkv"
    output_path = str(dir_path / output_file)  # Convert Path object to string

    # Run ffprobe to gather stream information
    ffprobe_cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "stream=codec_name,codec_type", "-of", "csv=p=0", input_file
    ]
    result = subprocess.run(ffprobe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    codec_info = result.stdout.strip().split('\n')

    # Initialize codec variables
    video_codec_info = ""
    audio_codec_info = ""
    subtitle_codec_info = ""

    # Read codec information line by line
    for line in codec_info:
        codec_name, codec_type = line.split(',')
        if codec_type == "video":
            video_codec_info = codec_name
        elif codec_type == "audio":
            audio_codec_info = codec_name
        elif codec_type == "subtitle":
            subtitle_codec_info = codec_name

    # Print the input file and codec details
    print(f"Processing: {input_file}")
    print("Detected Codecs:")
    print(f"  Video Codec   : {video_codec_info or 'Unknown'}")
    print(f"  Audio Codec   : {audio_codec_info or 'Unknown'}")
    print(f"  Subtitle Codec: {subtitle_codec_info or 'None'}")

    # Determine audio codec action: copy if it's AAC, AC3, or EAC3, else convert to AAC
    audio_action = "copy" if audio_codec_info in {"aac", "ac3", "eac3"} else "aac"

    # Handle subtitle stream: convert to a compatible format or discard if unsupported
    if not subtitle_codec_info:
        subtitle_action = ["-sn"]  # Discard subtitles if none or not compatible
    else:
        subtitle_action = ["-c:s", "copy"]  # Copy the subtitles if already in a compatible format

    # Construct and run the FFmpeg command for conversion, using -n to skip existing files
    ffmpeg_cmd = [
        "ffmpeg", "-n", "-i", input_file,
        "-c:v", "hevc_nvenc", "-profile:v", "main10", "-rc", "constqp", "-cq", "20",
        "-rc-lookahead", "32", "-g", "600", "-c:a", audio_action
    ]
    ffmpeg_cmd.extend(subtitle_action)  # Add subtitle action to the command
    ffmpeg_cmd.append(output_path)  # Add output file path

    # Run the FFmpeg command
    subprocess.run(ffmpeg_cmd)

    # Calculate file size and check against limit
    file_size = os.path.getsize(output_path)
    if size_limit_bytes > 0 and file_size >= size_limit_bytes:
        print(f"Size limit of {size_limit_bytes} bytes reached. Stopping conversions.")
        return conversion_count + 1, file_size

    print(f"Output saved to: {output_path}")
    print("------------------------------------")
    return conversion_count + 1, file_size

def main():
    args = parse_arguments()
    conversion_limit = args.limit
    size_limit_bytes = convert_size_to_bytes(args.size)

    conversion_count = 0
    size_written = 0

    # Loop through all video files in the directory recursively
    for root, _, files in os.walk("."):
        for file in files:
            if file.endswith((".mp4", ".mkv", ".avi")):
                if conversion_limit > 0 and conversion_count >= conversion_limit:
                    print(f"Reached the conversion limit of {conversion_limit} files.")
                    return

                input_file = os.path.join(root, file)
                conversion_count, file_size = process_video(input_file, size_limit_bytes, conversion_count)
                size_written += file_size

                if size_limit_bytes > 0 and size_written >= size_limit_bytes:
                    print(f"Size limit of {size_limit_bytes} bytes reached. Stopping conversions.")
                    return

    print(f"Conversion completed. Total files processed: {conversion_count}.")

if __name__ == "__main__":
    main()
