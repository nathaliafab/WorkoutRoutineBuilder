import json
import logging
import os
import random
from io import BytesIO

import numpy as np
import requests
from dotenv import load_dotenv
from googleapiclient.discovery import build
from PIL import Image as PILImage, ImageEnhance as PILImageEnhance, ImageOps

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Image, Spacer, HRFlowable


def setup_logging(log_file_path="logfile.log"):
    """Configure logging to write to a specified file."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    if logger.hasHandlers():
        logger.handlers.clear()

    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.info("Logging setup complete.")
    return logger


def initialize_youtube_api():
    """Initialize YouTube API client using credentials from environment variables."""
    load_dotenv()
    api_key = os.getenv("YOUTUBE_API_KEY")

    if not api_key:
        logger.error("YouTube API key is not set in environment variables.")
        raise ValueError("YouTube API key is not set in environment variables.")

    youtube_client = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
    logger.info("YouTube API client initialized.")
    return youtube_client


def fetch_youtube_videos(channel_id, category, excluded_keywords, max_results=7):
    """Fetch YouTube videos from a specific channel and category, excluding Shorts, and organize them by category."""
    logger.info(
        "Fetching videos from channel '%s' for category '%s'.",
        channel_id,
        category["category_name"],
    )

    keywords = category.get("keywords", [])

    try:
        videos = fetch_videos_from_youtube(channel_id, keywords, max_results)
        categorized_videos = categorize_videos(videos, category, excluded_keywords)

    except Exception as err:
        logger.error("An error occurred while fetching or categorizing videos: %s", err)
        categorized_videos = {"daily": [], "include": []}

    return categorized_videos


def fetch_videos_from_youtube(channel_id, keywords, max_results=7):
    """Fetch YouTube videos from a specific channel and query, excluding Shorts."""
    logger.info(
        "Fetching videos from channel '%s' with keywords: %s", channel_id, keywords
    )

    try:
        search_response = (
            youtube.search()
            .list(
                part="snippet",
                channelId=channel_id,
                q=" ".join(keywords),
                type="video",
                order="date",  # Latest videos first
                maxResults=max_results,
                videoDuration="long",  # >20 minutes. Could be also 'medium' (4-20 minutes). It's important to filter out Shorts.
            )
            .execute()
        )

        video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]
        if not video_ids:
            logger.warning("No videos found for the given query.")
            return [], {}

        video_details = fetch_video_details(video_ids)

        videos = [
            {
                "id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                "thumb": item["snippet"]["thumbnails"]["high"]["url"],
                "duration": video_details.get(item["id"]["videoId"], 0),
            }
            for item in search_response.get("items", [])
        ]

        logger.info("Fetched %d videos from channel '%s'.", len(videos), channel_id)
        return videos

    except Exception as err:
        logger.error("An error occurred while fetching videos: %s", err)
        return []


def categorize_videos(videos, category, excluded_keywords):
    """Organize videos into categories based on the provided category information."""
    logger.info(
        "Organizing %d videos into category '%s'.",
        len(videos),
        category["category_name"],
    )

    categorized_videos = {"daily": [], "include": []}

    for video in videos:
        title = video.get("title")
        if not title:
            logger.debug("Skipping video with missing title: %s", video)
            continue

        if any(keyword in title.lower() for keyword in excluded_keywords):
            logger.debug("Skipping video due to excluded keywords: %s", title)
            continue

        if category.get("daily", False):
            categorized_videos["daily"].append(video)
            logger.info(
                "Added video to 'daily' list in category '%s': %s",
                category["category_name"],
                title,
            )
        else:
            categorized_videos["include"].append(video)
            logger.info(
                "Added video to 'include' list in category '%s': %s",
                category["category_name"],
                title,
            )

    logger.info(
        "Categorized videos for category '%s'. Total videos: daily %d, include %d",
        category["category_name"],
        len(categorized_videos["daily"]),
        len(categorized_videos["include"]),
    )
    return categorized_videos


def fetch_video_details(video_ids):
    """Fetch video details for multiple video IDs."""
    logger.info("Fetching video details for IDs: %s", video_ids)

    try:
        video_response = (
            youtube.videos()
            .list(part="contentDetails", id=",".join(video_ids))
            .execute()
        )

        details = {
            item["id"]: parse_duration_to_minutes(item["contentDetails"]["duration"])
            for item in video_response.get("items", [])
        }
        logger.info("Fetched video details for %d videos.", len(details))
        return details
    except Exception as err:
        logger.error("An error occurred while fetching video details: %s", err)
        return {}


def parse_duration_to_minutes(duration):
    """Parse ISO 8601 duration format to minutes."""
    logger.debug("Parsing duration: %s", duration)

    if not duration.startswith("PT"):
        logger.warning("Unexpected duration format: %s", duration)
        return 0

    duration = duration[2:]  # Remove 'PT' prefix
    minutes = 0

    try:
        if "H" in duration:
            hours, duration = duration.split("H", 1)
            minutes += int(hours) * 60

        if "M" in duration:
            minutes_part, duration = duration.split("M", 1)
            if minutes_part:
                minutes += int(minutes_part)

        if "S" in duration:
            seconds = int(duration.replace("S", ""))
            minutes += seconds // 60
    except ValueError as e:
        logger.error("Error parsing duration '%s': %s", duration, e)
        return 0

    logger.debug("Parsed duration to minutes: %d", minutes)
    return minutes


def generate_week_schedule(
    categorized_videos,
    rest_days,
    min_daily_duration,
    max_daily_duration,
    min_videos_per_day,
    max_videos_per_day,
):
    """Generate a weekly schedule ensuring videos fit the daily time constraints and category constraints."""
    logger.info("Generating weekly schedule.")

    all_days = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    available_days = [day for day in all_days if not rest_days.get(day, False)]

    if not available_days:
        raise ValueError(
            "No available days for scheduling. Please update the rest days configuration."
        )

    logger.info("Available days for scheduling: %s", available_days)

    daily_categories = categorized_videos.get("daily", [])
    weekly_categories = categorized_videos.get("include", [])

    logger.debug("Daily categories: %s", daily_categories)
    logger.debug("Weekly categories: %s", weekly_categories)

    week_schedule = {day: [] for day in all_days}
    all_weekly_videos = [
        video for video in weekly_categories if isinstance(video, dict)
    ]

    logger.debug("All weekly videos: %s", all_weekly_videos)

    for day in available_days:
        day_videos = []
        total_duration = 0

        if daily_categories:
            daily_video = random.choice(daily_categories)
            if daily_video.get("duration", 0) <= max_daily_duration:
                day_videos.append(daily_video)
                total_duration += daily_video["duration"]
                logger.info(
                    "Added daily video for %s: %s (Duration: %d min)",
                    day,
                    daily_video["title"],
                    daily_video["duration"],
                )

        available_weekly_videos = [
            video
            for video in all_weekly_videos
            if video.get("duration", 0) <= max_daily_duration
        ]
        random.shuffle(available_weekly_videos)
        logger.debug("Shuffled weekly videos: %s", available_weekly_videos)

        for video in available_weekly_videos:
            if (
                len(day_videos) >= max_videos_per_day
                or total_duration >= max_daily_duration
            ):
                break
            if total_duration + video["duration"] <= max_daily_duration:
                day_videos.append(video)
                total_duration += video["duration"]
                logger.info(
                    "Added weekly video for %s: %s (Duration: %d min)",
                    day,
                    video["title"],
                    video["duration"],
                )

        if len(day_videos) < min_videos_per_day or total_duration < min_daily_duration:
            remaining_videos = [
                video for video in all_weekly_videos if video not in day_videos
            ]
            random.shuffle(remaining_videos)
            logger.debug(
                "Remaining videos for additional allocation: %s", remaining_videos
            )

            while (
                len(day_videos) < min_videos_per_day
                and total_duration < max_daily_duration
                and remaining_videos
            ):
                valid_videos = [
                    video
                    for video in remaining_videos
                    if total_duration + video["duration"] <= max_daily_duration
                ]

                if not valid_videos:
                    logger.info(
                        "No more valid videos to add without exceeding daily duration."
                    )
                    break

                video = random.choice(valid_videos)
                day_videos.append(video)
                total_duration += video["duration"]
                remaining_videos.remove(video)
                logger.info(
                    "Added additional video for %s: %s (Duration: %d min)",
                    day,
                    video["title"],
                    video["duration"],
                )

        week_schedule[day] = day_videos[:max_videos_per_day]
        logger.info(
            "Final schedule for %s: %d videos, total duration %d min",
            day,
            len(day_videos),
            total_duration,
        )

    return week_schedule


def remove_black_borders(image, tolerance=30):
    """Remove black borders from the top and bottom of an image."""
    logger.debug("Removing black borders with tolerance: %d", tolerance)

    grayscale_image = ImageOps.grayscale(image)
    image_array = np.array(grayscale_image)
    mask = image_array < tolerance
    non_black_rows = np.any(~mask, axis=1)
    top = np.argmax(non_black_rows)
    bottom = len(non_black_rows) - np.argmax(non_black_rows[::-1]) - 1

    return image.crop((0, top, image.width, bottom + 1))


def get_image_from_url(url):
    """Get an image from a URL, remove black borders, and return it as a PIL Image."""
    logger.info("Fetching image from URL: %s", url)

    try:
        response = requests.get(url)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type")
        if "image" not in content_type:
            logger.error(
                "URL does not point to an image. Content-Type: %s", content_type
            )
            return None

        img = PILImage.open(BytesIO(response.content)).convert("RGB")
        img = remove_black_borders(img)
        return img
    except Exception as e:
        logger.error("Error loading image from URL %s: %s", url, e)
        return None


def resize_image(image, max_width, max_height):
    """Resize image while maintaining aspect ratio with high quality."""
    logger.debug("Resizing image to fit within %d x %d", max_width, max_height)

    original_width, original_height = image.size
    aspect_ratio = original_width / original_height

    if original_width > max_width or original_height > max_height:
        if (max_width / max_height) > aspect_ratio:
            new_width = int(max_height * aspect_ratio)
            new_height = max_height
        else:
            new_width = max_width
            new_height = int(max_width / aspect_ratio)

        new_width = int(new_width)
        new_height = int(new_height)
        image = image.resize((new_width, new_height), resample=PILImage.LANCZOS)
        enhancer = PILImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.5)

    return image


def save_schedule_as_pdf(
    schedule, filename="weekly_routine.pdf", show_thumbnail=True, show_duration=True
):
    """Save the weekly schedule as a PDF with enhanced visual appeal and color-coded dividers."""
    logger.info("Starting to save weekly routine as a PDF.")

    document = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    pdf_title_style = ParagraphStyle(
        "PDFTitle",
        parent=styles["Title"],
        fontSize=24,
        spaceAfter=12,
        textColor=colors.darkslategrey,
        alignment=1,
        fontName="Times-Roman",
    )

    day_heading_style = ParagraphStyle(
        "DayHeading",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=4,
        alignment=0,
        textColor=colors.darkviolet,
        fontName="Times-Roman",
    )

    video_title_style = ParagraphStyle(
        "VideoTitle",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=4,
        textColor=colors.darkslategrey,
        alignment=0,
        fontName="Helvetica-Bold",
    )

    video_url_style = ParagraphStyle(
        "VideoURL",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=8,
        textColor=colors.blueviolet,
        alignment=0,
        underline=True,
        fontName="Helvetica",
    )

    duration_style = ParagraphStyle(
        "DurationStyle",
        parent=styles["Normal"],
        fontSize=12,
        spaceAfter=8,
        textColor=colors.violet,
        alignment=0,
        fontName="Helvetica",
    )

    header = Paragraph("<b>WEEKLY WORKOUT ROUTINE</b>", pdf_title_style)
    elements.append(header)
    elements.append(Spacer(1, 12))

    pastel_colors = [
        colors.pink,
        colors.lightblue,
        colors.mistyrose,
        colors.lightgreen,
        colors.lightsteelblue,
        colors.lavender,
        colors.lightyellow,
    ]

    for i, (day, videos) in enumerate(schedule.items()):
        total_duration = sum(video["duration"] for video in videos)
        if total_duration == 0:
            duration_text = "<i>Rest Day</i>"
        else:
            duration_text = f" ({total_duration} min)"

        day_heading = Paragraph(f"<b>{day}</b>", day_heading_style)
        elements.append(day_heading)

        if show_duration:
            duration_paragraph = Paragraph(duration_text, duration_style)
            elements.append(duration_paragraph)

        elements.append(Spacer(1, 8))

        for video in videos:
            video_title = video["title"]
            video_url = video["url"]
            video_thumb_url = video["thumb"]

            if show_thumbnail:
                try:
                    img = get_image_from_url(video_thumb_url)
                    if img:
                        img = resize_image(img, 2 * inch, 2 * inch)
                        buffer = BytesIO()
                        img.save(buffer, format="JPEG", quality=95)
                        buffer.seek(0)
                        thumb_image = Image(buffer)
                        thumb_image.drawHeight = img.height
                        thumb_image.drawWidth = img.width
                        thumb_image.hAlign = "LEFT"
                        elements.append(thumb_image)
                        logger.info("Added thumbnail for video: %s", video_title)
                except Exception as e:
                    logger.error(
                        "Error including thumbnail for video %s: %s", video_title, e
                    )
                    elements.append(
                        Paragraph("Error loading thumbnail", video_title_style)
                    )
                    elements.append(Spacer(1, 8))

            video_title_paragraph = Paragraph(
                f"<b>{video_title}</b>", video_title_style
            )
            video_url_paragraph = Paragraph(
                f'<a href="{video_url}">{video_url}</a>', video_url_style
            )
            elements.append(video_title_paragraph)
            elements.append(video_url_paragraph)
            elements.append(Spacer(1, 8))

        divider_color = pastel_colors[i % len(pastel_colors)]
        divider = HRFlowable(
            width="100%",
            thickness=2,
            color=divider_color,
            spaceBefore=12,
            spaceAfter=12,
        )
        elements.append(divider)

    document.build(elements)
    logger.info("Weekly routine has been saved as a PDF as %s.", filename)


def main():
    """Main function to execute the script."""
    logger.info("Starting script execution.")

    try:
        with open("input_data.json", "r") as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error("Error loading input data: %s", e)
        return

    categorized_videos = {"daily": [], "include": []}
    excluded_keywords = data.get("excluded_keywords", [])
    youtube_channels = data.get("youtube_channels", [])
    exercise_categories = data.get("exercise_categories", [])

    for channel in youtube_channels:
        if channel.get("include"):
            channel_id = channel.get("channel_id")
            for category in exercise_categories:
                if category.get("include"):
                    try:
                        category_videos = fetch_youtube_videos(
                            channel_id, category, excluded_keywords
                        )
                        categorized_videos["daily"].extend(
                            category_videos.get("daily", [])
                        )
                        categorized_videos["include"].extend(
                            category_videos.get("include", [])
                        )
                    except Exception as e:
                        logger.error(
                            "Error fetching videos for channel %s, category %s: %s",
                            channel_id,
                            category.get("category_name", "Unknown"),
                            e,
                        )

    total_videos = len(categorized_videos["daily"]) + len(categorized_videos["include"])
    logger.info("Number of videos fetched: %d", total_videos)

    if total_videos == 0:
        logger.warning(
            "No videos were fetched. Check the YouTube API queries and input data."
        )
        return

    unique_videos = {}
    for category, videos in categorized_videos.items():
        for video in videos:
            unique_videos[video["url"]] = (video, category)

    categorized_videos = {
        "daily": [video for video, cat in unique_videos.values() if cat == "daily"],
        "include": [video for video, cat in unique_videos.values() if cat == "include"],
    }

    unique_total_videos = len(categorized_videos["daily"]) + len(
        categorized_videos["include"]
    )
    logger.info("Number of unique videos: %d", unique_total_videos)
    logger.debug("Categorized videos: %s", categorized_videos)

    if unique_total_videos == 0:
        logger.warning("No unique videos available after deduplication.")
        return

    try:
        schedule_params = data.get("daily_video_schedule", {})
        schedule = generate_week_schedule(
            categorized_videos,
            data.get("rest_days", {}),
            schedule_params.get("min_duration_minutes"),
            schedule_params.get("max_duration_minutes"),
            schedule_params.get("min_videos_per_day"),
            schedule_params.get("max_videos_per_day"),
        )

        additional_settings = data.get("additional_settings", {})
        save_schedule_as_pdf(
            schedule,
            show_thumbnail=additional_settings.get("show_thumbnail", False),
            show_duration=additional_settings.get("show_duration", False),
        )

        logger.info("Script execution completed successfully.")
    except Exception as e:
        logger.error("Error generating schedule or saving PDF: %s", e)


if __name__ == "__main__":
    logger = setup_logging()
    youtube = initialize_youtube_api()
    main()
