#!/usr/bin/env python3

import argparse
import os
import pathlib
import random
import sys
import time
import threading
import gpiod
import gpiodevice
from gpiod.line import Bias, Direction, Value, Edge

from PIL import Image

from inky.auto import auto

synologyInkyPath = "/mnt/synology/inky"

# Global variables for LED blinking control
led_blinking = False
led_blink_thread = None
led_gpio_request = None
led_line_offset = None

def get_all_image_files(folder=synologyInkyPath):
    """
    Returns a list of all image file paths from the specified folder.
    
    Args:
        folder: Path to the folder containing images
        
    Returns:
        List of full paths to all image files
        
    Raises:
        ValueError: If no valid image files are found in the folder
    """
    # Define supported image extensions
    image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".bmp")
    
    # Get all image files from the folder
    image_files = [f for f in os.listdir(folder) if f.lower().endswith(image_extensions)]
    
    if not image_files:
        raise ValueError(f"No image files found in {folder}")
    
    # Return full paths
    return [os.path.join(folder, f) for f in image_files]

def get_random_image_path(folder=synologyInkyPath):
    """
    Returns a random image path from the specified folder.
    
    Args:
        folder: Path to the folder containing images
        
    Returns:
        Full path to a randomly selected image file
        
    Raises:
        ValueError: If no valid image files are found in the folder
    """
    all_images = get_all_image_files(folder)
    return random.choice(all_images)

def get_latest_image_path(folder=synologyInkyPath):
    """
    Returns the most recently modified image file path from the specified folder.
    
    Args:
        folder: Path to the folder containing images
        
    Returns:
        Full path to the most recently modified image file
        
    Raises:
        ValueError: If no valid image files are found in the folder
    """
    all_images = get_all_image_files(folder)
    
    # Sort by modification time (most recent first)
    latest_image = max(all_images, key=os.path.getmtime)
    
    return latest_image

def resize_image_aspect_fit(image, target_size, background_color="white"):
    """
    Resize an image to fit within target_size while maintaining aspect ratio.
    Centers the image and fills the remaining space with the background color.
    
    Args:
        image: PIL Image object
        target_size: Tuple of (width, height) for the target display size
        background_color: Color to use for letterbox/pillarbox areas (default: "white")
        
    Returns:
        PIL Image object resized and centered with aspect ratio preserved
    """
    target_width, target_height = target_size
    
    # Calculate the aspect ratios
    image_aspect = image.width / image.height
    target_aspect = target_width / target_height
    
    # Determine the scaling factor to fit the image within the target size
    if image_aspect > target_aspect:
        # Image is wider - fit to width
        new_width = target_width
        new_height = int(target_width / image_aspect)
    else:
        # Image is taller - fit to height
        new_height = target_height
        new_width = int(target_height * image_aspect)
    
    # Resize the image maintaining aspect ratio
    resized = image.resize((new_width, new_height), Image.LANCZOS)
    
    # Create a new image with the target size and background color
    result = Image.new(image.mode, target_size, background_color)
    
    # Calculate position to center the resized image
    x_offset = (target_width - new_width) // 2
    y_offset = (target_height - new_height) // 2
    
    # Paste the resized image onto the background
    result.paste(resized, (x_offset, y_offset))
    
    return result

def setup_led():
    """Setup the LED GPIO pin and return the gpio request and line offset."""
    global led_gpio_request, led_line_offset
    
    LED_PIN = 13
    chip = gpiodevice.find_chip_by_platform()
    led_line_offset = chip.line_offset_from_id(LED_PIN)
    led_gpio_request = chip.request_lines(
        consumer="inky-led", 
        config={led_line_offset: gpiod.LineSettings(direction=Direction.OUTPUT, bias=Bias.DISABLED)}
    )
    return led_gpio_request, led_line_offset

def set_led(state):
    """Set the LED on or off."""
    global led_gpio_request, led_line_offset
    if led_gpio_request and led_line_offset is not None:
        led_gpio_request.set_value(led_line_offset, Value.ACTIVE if state else Value.INACTIVE)

def blink_led_worker():
    """Worker function that blinks the LED every 500ms."""
    global led_blinking
    while led_blinking:
        set_led(True)
        time.sleep(0.5)
        if not led_blinking:  # Check again before turning off
            break
        set_led(False)
        time.sleep(0.5)

def start_led_blinking():
    """Start the LED blinking in a background thread."""
    global led_blinking, led_blink_thread
    
    if not led_blinking:
        led_blinking = True
        led_blink_thread = threading.Thread(target=blink_led_worker, daemon=True)
        led_blink_thread.start()

def stop_led_blinking():
    """Stop the LED blinking and turn it off."""
    global led_blinking, led_blink_thread
    
    if led_blinking:
        led_blinking = False
        if led_blink_thread:
            led_blink_thread.join(timeout=1.0)
        set_led(False)

def enable_led(enable):
    LED_PIN = 13
    # Find the gpiochip device we need, we'll use
    # gpiodevice for this, since it knows the right device
    # for its supported platforms.
    chip = gpiodevice.find_chip_by_platform()

    # Setup for the LED pin
    led = chip.line_offset_from_id(LED_PIN)
    gpio = chip.request_lines(consumer="inky", config={led: gpiod.LineSettings(direction=Direction.OUTPUT, bias=Bias.DISABLED)})

    if enable:
        gpio.set_value(led, Value.ACTIVE)
    else:
        gpio.set_value(led, Value.INACTIVE)

def show_image(image_path=None):
    """
    Display an image on the Inky display.
    
    Args:
        image_path: Optional path to image file. If not provided, will check command line args
                    or use a random image.
    """
    # Stop blinking and turn LED on solid while showing image
    stop_led_blinking()
    set_led(True)

    parser = argparse.ArgumentParser()

    parser.add_argument("--saturation", "-s", type=float, default=0.5, help="Colour palette saturation")
    parser.add_argument("--file", "-f", type=pathlib.Path, help="Image file")

    inky = auto(ask_user=True, verbose=True)

    args, _ = parser.parse_known_args()

    saturation = args.saturation

    # Determine which file to use (priority: function arg > command line arg > random)
    if image_path:
        file = image_path
    elif args.file:
        file = args.file
    else:
        print("no file provided fetching random image")
        file = get_random_image_path()

    print(f"Selected image: {file}")


    image = Image.open(file)
    resized_image = resize_image_aspect_fit(image, inky.resolution)

    try:
        inky.set_image(resized_image, saturation=saturation)
    except TypeError:
        inky.set_image(resized_image)

    inky.show()

    # Resume blinking after image is shown
    start_led_blinking()

def setup_buttons():
    # Setup LED first
    setup_led()
    
    SW_A = 5
    SW_B = 6
    SW_C = 25
    SW_D = 24

    BUTTONS = [SW_A, SW_B, SW_C, SW_D]

    # These correspond to buttons A, B, C and D respectively
    LABELS = ["A", "B", "C", "D"]

    # Create settings for all the input pins, we want them to be inputs
    # with a pull-up and a falling edge detection.
    INPUT = gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.PULL_UP, edge_detection=Edge.FALLING)

    # Find the gpiochip device we need, we'll use
    # gpiodevice for this, since it knows the right device
    # for its supported platforms.
    chip = gpiodevice.find_chip_by_platform()

    # Build our config for each pin/line we want to use
    OFFSETS = [chip.line_offset_from_id(id) for id in BUTTONS]
    line_config = dict.fromkeys(OFFSETS, INPUT)

    # Request the lines, *whew*
    request = chip.request_lines(consumer="spectra6-buttons", config=line_config)


    # "handle_button" will be called every time a button is pressed
    # It receives one argument: the associated gpiod event object.
    def handle_button(event):
        index = OFFSETS.index(event.line_offset)
        gpio_number = BUTTONS[index]
        label = LABELS[index]
        print(f"Button press detected on GPIO #{gpio_number} label: {label}")
        
        if label == "A":
            # Button A: Show random image
            print("Fetching random image...")
            random_image = get_random_image_path()
            show_image(random_image)
        elif label == "B":
            # Button B: Show latest image
            print("Fetching latest image...")
            latest_image = get_latest_image_path()
            show_image(latest_image)

    # Start LED blinking while waiting for button presses
    start_led_blinking()
    print("Ready! LED is blinking.")
    print("Press button A for random image, button B for latest image.")

    while True:
        for event in request.read_edge_events():
           handle_button(event)

setup_buttons()