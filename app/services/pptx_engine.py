from pptx import Presentation
from pptx.util import Inches, Pt
import io

def generate_pptx(slide_data: list) -> bytes:
    """
    Generates a PPTX file from a list of slide dictionaries.
    Each dictionary should have 'title' and 'content' keys.
    """
    prs = Presentation()

    for slide_info in slide_data:
        title_text = slide_info.get("title", "Untitled")
        
        # Determine content. Can be 'content' or 'points' (list)
        content_raw = slide_info.get("content", "")
        points = slide_info.get("points", [])
        
        if isinstance(points, list) and points:
            # Join list into bullet points if provided as logic
            content_text = "\n".join(points)
        else:
            content_text = str(content_raw)

        # Use the Bullet Layout (typically index 1)
        # 0 = Title Slide, 1 = Title and Content
        slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(slide_layout)

        # Set Title
        title = slide.shapes.title
        if title:
            title.text = title_text

        # Set Content
        # In standard layouts, placeholder[1] is the body
        if len(slide.placeholders) > 1:
            body_shape = slide.placeholders[1]
            tf = body_shape.text_frame
            tf.text = content_text
            
            # Optional: formatting could go here
            # for paragraph in tf.paragraphs:
            #     paragraph.font.size = Pt(18)

    output = io.BytesIO()
    prs.save(output)
    output.seek(0)
    return output.read()
