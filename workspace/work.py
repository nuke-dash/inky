#!/usr/bin/env python3

import argparse
import os
import pathlib
import random
import sys
import time
import gpiod
import gpiodevice
from gpiod.line import Bias, Direction, Value

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
resizedImage = image.resize(inky.resolution)

try:
    inky.set_image(resizedImage, saturation=saturation)
except TypeError:
    inky.set_image(resizedImage)

inky.show()

time.sleep(30)
enable_led(False)