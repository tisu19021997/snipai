IMAGE_DESCRIPTION_TO_TAGS_PROMPT = """\
# Task:
Select the most relevant tag for an image based on its description.

# Instructions:
1. Read the provided image description
2. Select UP TO 2 tags from the following list: {available_tags}
3. Only use tags from the provided list. Never create new tags
4. Return your response in JSON format with the key "names"

# Required JSON Output Format:
{{"names": ["tag1", "tag2"]}} or {{"names": ["tag1"]}}

# Examples:

## Input:
The image shows a single jacket laid out on its side against a gray concrete wall. The jacket is predominantly brown in color and features a zipper running down the front, with two pockets on either side of the chest area. The collar of the jacket is black, providing a striking contrast to the brown fabric. The sleeves are long enough to cover the wrists, and the hood is also black, matching the collar.

## Tag list:
["clothes", "art", "book", "landscape", "cute animal"]

## Output:
{{"names": ["clothes"]}}

## Input:

The image is a vibrant and colorful abstract art piece featuring various shapes in shades of red, blue, yellow, green, and black. The shapes are arranged in a seemingly random yet harmonious manner, creating an intriguing visual effect. The background of the image is white, which contrasts with the colorful shapes and makes them stand out even more.\n\nThe image also contains text that reads "okazsp" and "1".

## Tag list:
["cafe shop", "tree", "xmas", "sneaker", "art", "food"]

## Output:
{{"names": ["art"]}}"""
