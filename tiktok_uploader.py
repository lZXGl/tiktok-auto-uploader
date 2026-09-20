import os
import sys
import shutil
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

# Setup base directories
DEFAULT_PROFILE_DIR = Path.home() / ".tiktok_profile"
DEFAULT_SOURCE = Path.cwd() / "final"
DEFAULT_ARCHIVE = Path.cwd() / "uploaded"

def parse_args():
    parser = argparse.ArgumentParser(description="TikTok Automated Video Uploader")
    parser.add_argument("--login", action="store_true", help="Launch headful browser to log in and save session.")
    parser.add_argument("--source", type=str, default=DEFAULT_SOURCE, help="Path to folder containing videos.")
    parser.add_argument("--archive", type=str, default=DEFAULT_ARCHIVE, help="Path to folder to move uploaded videos to.")
    parser.add_argument("--hashtag", type=str, default="#Automation", help="Hashtag(s) to add to the caption.")
    parser.add_argument("--caption", type=str, default="", help="Video caption prefix.")
    parser.add_argument("--headless", action="store_true", help="Run the browser in headless mode during upload.")
    parser.add_argument("--timeout", type=int, default=1200, help="Max upload/processing timeout in seconds (default: 1200s / 20m).")
    return parser.parse_args()

def handle_login(profile_dir):
    print(f"Launching browser to log in... Session will be saved to: {profile_dir}")
    with sync_playwright() as p:
        # Launch headful browser for login
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        )
        page = context.new_page()
        page.goto("https://www.tiktok.com")
        
        print("\n" + "="*60)
        print("ACTION REQUIRED:")
        print("1. Log in to your TikTok account in the opened browser window.")
        print("2. Complete any required CAPTCHAs/verifications.")
        print("3. Verify you are logged in and looking at your home feed.")
        print("4. Come back to this terminal and press Enter to save your session...")
        print("="*60 + "\n")
        
        input("Press Enter once logged in...")
        context.close()
    print("Session saved successfully! You can now run the script in upload mode.")

def upload_video(video_path, archive_dir, hashtag, caption_prefix, profile_dir, headless, timeout):
    print(f"Starting upload for: {video_path.name}")
    
    with sync_playwright() as p:
        # Launch Playwright with the saved session profile
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.new_page()
        
        # Navigate to the TikTok upload page
        print("Navigating to TikTok upload page...")
        page.goto("https://www.tiktok.com/tiktokstudio/upload?from=webapp&tab=video", wait_until="domcontentloaded")
        
        # Wait a bit for page to initialize
        page.wait_for_timeout(5000)
        
        # If we got redirected to login page, session might have expired
        if "login" in page.url:
            print("Error: You are not logged in! Please run with --login first.")
            context.close()
            sys.exit(1)

        # Upload the video file using the hidden file input
        print("Waiting for file input to load...")
        file_input = None
        target_page = None
        
        # Poll for 30 seconds to allow the page/iframe to finish loading
        for _ in range(30):
            # Check main page
            input_el = page.locator('input[type="file"]')
            if input_el.count() > 0:
                file_input = input_el
                target_page = page
                break
                
            # Check all frames
            for frame in page.frames:
                input_el = frame.locator('input[type="file"]')
                if input_el.count() > 0:
                    print("Found file input inside an iframe.")
                    file_input = input_el
                    target_page = frame
                    break
            if file_input:
                break
            page.wait_for_timeout(1000)
            
        if not file_input:
            raise Exception("Could not find file input on the page or any iframe after 30 seconds.")
            
        print("Uploading video file...")
        file_input.set_input_files(str(video_path))
        target_page = target_page
            
        print("Video file selected. Waiting for upload form to populate...")
        target_page.wait_for_timeout(8000)

        # Fill in the caption and hashtag
        print("Setting caption and hashtags...")
        caption_editor = target_page.locator('[contenteditable="true"]').first
        caption_editor.wait_for(state="visible", timeout=20000)
        
        # Focus and clear the existing text
        caption_editor.focus()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.wait_for_timeout(1000)
        
        # Type the caption and hashtag character-by-character
        if caption_prefix:
            print("Typing caption prefix character-by-character...")
            for char in f"{caption_prefix} ":
                page.keyboard.insert_text(char)
                page.wait_for_timeout(150)
            
        print("Typing hashtag character-by-character to trigger suggestions...")
        for char in hashtag:
            if char == '#':
                page.keyboard.type(char)
            else:
                page.keyboard.insert_text(char)
            page.wait_for_timeout(200)
        
        # Wait 20 seconds for the suggestions list to load
        print("Waiting 20 seconds for suggestion dropdown to populate...")
        page.wait_for_timeout(20000)
        
        # Press Enter to select the recommendation
        print("Selecting first suggestion via keyboard navigation (Enter)...")
        page.keyboard.press("Enter")
        page.wait_for_timeout(2000)
        # 1. Wait for upload progress indicator to appear and then disappear (upload completes)
        print("Waiting for upload progress to start (checking for progress indicators)...")
        
        progress_selectors = [
            '[data-e2e="upload-progress"]',
            '[role="progressbar"]',
            'div:has-text("Uploading")',
            'div:has-text("%")'
        ]
        
        progress_locator = None
        has_progress = False
        import re
        
        # Wait up to 90 seconds for any progress indicator to appear
        for check_sec in range(90):
            for selector in progress_selectors:
                loc = target_page.locator(selector)
                if loc.count() > 0 and loc.first.is_visible():
                    if "%" in selector:
                        text = loc.first.inner_text()
                        if not re.search(r'\d+%', text):
                            continue
                    print(f"Upload progress indicator detected via selector '{selector}' after {check_sec}s. Monitoring upload...")
                    progress_locator = loc.first
                    has_progress = True
                    break
            if has_progress:
                break
            page.wait_for_timeout(1000)
            
        if has_progress:
            poll_interval = 10
            max_loops = max(1, timeout // poll_interval)
            print(f"Monitoring progress... Max wait time: {timeout}s.")
            for loop_idx in range(max_loops):
                is_visible = progress_locator.is_visible()
                if not is_visible:
                    # Double check if another selector still shows progress
                    still_active = False
                    for selector in progress_selectors:
                        loc = target_page.locator(selector)
                        if loc.count() > 0 and loc.first.is_visible():
                            if "%" in selector:
                                text = loc.first.inner_text()
                                if not re.search(r'\d+%', text):
                                    continue
                            progress_locator = loc.first
                            still_active = True
                            break
                    if not still_active:
                        print("Upload progress indicator disappeared! Video upload completed.")
                        break
                
                elapsed = (loop_idx + 1) * poll_interval
                try:
                    percent_text = progress_locator.inner_text()
                    print(f"[{elapsed}s elapsed] Upload status: {percent_text.strip()}")
                except Exception:
                    print(f"[{elapsed}s elapsed] Video is still uploading...")
                page.wait_for_timeout(poll_interval * 1000)
        else:
            print("No explicit progress indicator detected. Waiting a safety timeout of 3 minutes for slow connection...")
            page.wait_for_timeout(180000)

        # 2. Wait for the Post button to become visible and active
        print("Waiting for Post button to become active...")
        post_button = target_page.locator('[data-e2e="post_video_button"]').first
        post_button.wait_for(state="visible", timeout=60000)
        
        uploaded_successfully = False
        # Wait up to 5 minutes (30 loops of 10s) for processing checks to finish
        for loop_idx in range(30):
            is_disabled = post_button.evaluate("el => el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true'")
            if not is_disabled:
                is_disabled = post_button.evaluate("el => el.className.includes('disabled')")
            if not is_disabled:
                print("Post button is active! Posting...")
                try:
                    post_button.click(timeout=5000)
                except Exception as click_err:
                    print(f"Standard click failed ({click_err}), attempting force click...")
                    post_button.click(force=True)
                uploaded_successfully = True
                break
            elapsed = (loop_idx + 1) * 10
            print(f"[{elapsed}s elapsed] Video is still processing (Post button is disabled)...")
            page.wait_for_timeout(10000)
            
        if not uploaded_successfully:
            raise Exception("Timeout: Video processing took too long or Post button did not become active.")     
        # Wait for post request to finish/confirm
        print("Waiting 15 seconds for post request to finish...")
        page.wait_for_timeout(15000)
        
        # Close browser
        context.close()

    # Move video to archive folder
    archive_dir = Path(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    destination_path = archive_dir / video_path.name
    print(f"Moving uploaded video to archive: {destination_path}")
    shutil.move(str(video_path), str(destination_path))
    print("Video uploaded and archived successfully!")

def main():
    args = parse_args()
    
    # 1. Login Mode
    if args.login:
        handle_login(DEFAULT_PROFILE_DIR)
        sys.exit(0)
        
    # 2. Upload Mode
    source_dir = Path(args.source)
    archive_dir = Path(args.archive)
    source_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)
        
    # Get all video files in source directory (mp4, mkv, avi, mov)
    video_extensions = {".mp4", ".mkv", ".avi", ".mov"}
    video_files = [f for f in source_dir.iterdir() if f.is_file() and f.suffix.lower() in video_extensions]
    
    print(f"Found {len(video_files)} video(s) in source directory: '{source_dir}'")
    
    if len(video_files) == 0:
        print("No videos found to upload. Exiting.")
        sys.exit(0)
        
    # Pick the first video (oldest by modification time to process in order)
    video_files.sort(key=lambda x: x.stat().st_mtime)
    selected_video = video_files[0]
    
    # Run the upload process
    upload_video(
        video_path=selected_video,
        archive_dir=archive_dir,
        hashtag=args.hashtag,
        caption_prefix=args.caption,
        profile_dir=DEFAULT_PROFILE_DIR,
        headless=args.headless,
        timeout=args.timeout
    )

if __name__ == "__main__":
    main()
