#!/usr/bin/env python3

import argparse
import os
import pathlib
import random
import sys
import time
import gpiod
import gpiodevice
from gpiod.line import Bias, Direction, Value, Edge

from PIL import Image

from inky.auto import auto

synologyInkyPath = "/mnt/synology/inky"

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
    # Define supported image extensions
    image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".bmp")
    
    # Get all image files from the folder
    imgs = [f for f in os.listdir(folder) if f.lower().endswith(image_extensions)]
    
    if not imgs:
        raise ValueError(f"No image files found in {folder}")
    
    # Return a random image path
    return os.path.join(folder, random.choice(imgs))

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

def show_image():
    enable_led(True)

    parser = argparse.ArgumentParser()

    parser.add_argument("--saturation", "-s", type=float, default=0.5, help="Colour palette saturation")
    parser.add_argument("--file", "-f", type=pathlib.Path, help="Image file")

    inky = auto(ask_user=True, verbose=True)

    args, _ = parser.parse_known_args()

    saturation = args.saturation

    file = args.file
    if not file:
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

    time.sleep(30)
    enable_led(False)

def setup_buttons():
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
            show_image()


    while True:
        for event in request.read_edge_events():
           handle_button(event)

setup_buttons()