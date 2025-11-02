import cv2


def draw_box_label(
    image,
    box,
    label=None,
    scale=1.0,
    thickness=1,
    text_color=(0, 0, 0),
    rect_color=(255, 255, 255),
    padding=5,
    box_color=(255, 255, 255),
    box_thickness=2,
):
    """
    Draws a bounding box with a label on the given image.

    Args:
        image (numpy.ndarray): The image on which to draw the box and label.
        box (tuple): The bounding box coordinates in xyxy format (left, top, right, bottom).
        label (str): The label text to display.
        scale (float): Font scale factor.
        thickness (int): Thickness of the text lines.
        text_color (tuple): Color of the text in BGR format.
        rect_color (tuple): Color of the background rectangle for the label in BGR format.
        padding (int): Padding around the text within the rectangle.
        box_color (tuple): Color of the bounding box in BGR format.
        box_thickness (int): Thickness of the bounding box lines.
    """
    left, top, right, bottom = map(int, box)

    # Draw the bounding box
    cv2.rectangle(image, (left, top), (right, bottom), box_color, box_thickness)

    if label is not None:
        # Get the size of the text
        (text_width, text_height), _ = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness
        )

        # Calculate the position for the label background rectangle
        rect_top_left = (left, top - text_height - 2 * padding)
        rect_bottom_right = (left + text_width + 2 * padding, top)

        # Draw the background rectangle for the label
        cv2.rectangle(image, rect_top_left, rect_bottom_right, rect_color, cv2.FILLED)

        # Draw the label text
        cv2.putText(
            image,
            label,
            (left + padding, top - padding),
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            text_color,
            thickness,
            lineType=cv2.LINE_AA,
        )
