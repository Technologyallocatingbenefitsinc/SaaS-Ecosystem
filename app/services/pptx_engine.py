from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
import io

# Define Styling Constants
THEMES = {
    "default": {
        "bg_color": (255, 255, 255),
        "title_color": (0, 0, 0),
        "body_color": (80, 80, 80),
        "accent_color": (59, 130, 246) # Blue-500
    },
    "dark": {
        "bg_color": (15, 23, 42),
        "title_color": (255, 255, 255),
        "body_color": (203, 213, 225),
        "accent_color": (139, 92, 246) # Violet-500
    },
    "corporate": {
        "bg_color": (255, 255, 255),
        "title_color": (30, 58, 138),
        "body_color": (71, 85, 105),
        "accent_color": (37, 99, 235) # Blue-600
    },
    "warm": {
        "bg_color": (255, 251, 235),
        "title_color": (120, 53, 15),
        "body_color": (146, 64, 14),
        "accent_color": (217, 119, 6) # Amber-600
    }
}

def draw_theme_layout(slide, theme_name, theme_colors, width, height):
    """Adds geometric shapes to creates a modern layout."""
    shapes = slide.shapes
    accent_rgb = RGBColor(*theme_colors["accent_color"])
    
    if theme_name == "corporate":
        # Left Accent Bar
        shape = shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.5), height)
        shape.fill.solid()
        shape.fill.fore_color.rgb = accent_rgb
        shape.line.fill.background() # No outline
    
    elif theme_name == "dark":
        # Top thin accent line
        shape = shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, width, Inches(0.1))
        shape.fill.solid()
        shape.fill.fore_color.rgb = accent_rgb
        shape.line.fill.background()
        
        # Bottom right accent circle
        circle = shapes.add_shape(MSO_SHAPE.OVAL, width - Inches(2), height - Inches(2), Inches(3), Inches(3))
        circle.fill.solid()
        circle.fill.fore_color.rgb = accent_rgb
        circle.fill.transparency = 0.8 # Fades out
        circle.line.fill.background()

    elif theme_name == "warm":
        # Soft top header block
        shape = shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, width, Inches(1.2))
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor(253, 230, 138) # Light yellow accent
        shape.line.fill.background()
        # Reposition title to be on top of this if needed, but z-order is tricky. 
        # Usually shapes added first are at back.

def generate_pptx(slide_data: list, watermark: bool = False, theme_name: str = "default", aspect_ratio: str = "16:9") -> bytes:
    """
    Generates a style-aware PPTX file interactively.
    """
    prs = Presentation()
    
    # Set Slide Size
    if aspect_ratio == "1:1": # Square Carousel
        prs.slide_width = Inches(10)
        prs.slide_height = Inches(10)
    else: # Default 16:9
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

    # Get Theme Colors
    theme = THEMES.get(theme_name, THEMES["default"])
    bg_rgb = RGBColor(*theme["bg_color"])
    title_rgb = RGBColor(*theme["title_color"])
    body_rgb = RGBColor(*theme["body_color"])
    
    for i, slide_info in enumerate(slide_data):
        title_text = slide_info.get("title", "Untitled")
        content_raw = slide_info.get("content", "")
        points = slide_info.get("points", [])
        
        # Create Slide (Blank layout gives us full control, but Title+Content is easier for placeholders)
        # using Blank (6) to allow custom shape drawing easily? 
        # No, let's stick to 1 but adjust positions if needed.
        # Actually, for "Modern", we often want custom text boxes.
        # Let's stick to layout 1 for robustness but style it heavily.
        slide_layout = prs.slide_layouts[1] 
        slide = prs.slides.add_slide(slide_layout)
        
        # --- Apply Background ---
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = bg_rgb
        
        # --- Draw Theme Geometry (At the back) ---
        draw_theme_layout(slide, theme_name, theme, prs.slide_width, prs.slide_height)

        # --- Set Title ---
        title = slide.shapes.title
        if title:
            title.text = title_text
            # Use 'warm' theme offset if header bar exists
            if theme_name == "warm":
                title.top = Inches(0.2)
            
            # Style Title
            for paragraph in title.text_frame.paragraphs:
                paragraph.font.color.rgb = title_rgb
                paragraph.font.bold = True
                paragraph.font.name = "Arial" # Safer font

        # --- Set Content ---
        if len(slide.placeholders) > 1:
            body_shape = slide.placeholders[1]
            
            # Adjust body position for Corporate layout (shift right past bar)
            if theme_name == "corporate":
                body_shape.left = Inches(1.0)
                body_shape.width = prs.slide_width - Inches(1.5)

            tf = body_shape.text_frame
            tf.clear() # Clear existing placeholder text
            
            if isinstance(points, list) and points:
                for i, point in enumerate(points):
                    p = tf.add_paragraph() if i > 0 else tf.paragraphs[0]
                    p.text = point
                    p.level = 0
                    p.font.color.rgb = body_rgb
                    p.font.size = Pt(24) # Increased font size for modern look
            else:
                tf.text = str(content_raw)
                for paragraph in tf.paragraphs:
                    paragraph.font.color.rgb = body_rgb
                    paragraph.font.size = Pt(24)
                
    if watermark:
        # Add Watermark Slide
        blank_layout = prs.slide_layouts[6] 
        slide = prs.slides.add_slide(blank_layout)
        
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = bg_rgb
        
        draw_theme_layout(slide, theme_name, theme, prs.slide_width, prs.slide_height)
        
        txBox = slide.shapes.add_textbox(Inches(1), prs.slide_height/2 - Inches(0.5), prs.slide_width - Inches(2), Inches(1))
        tf = txBox.text_frame
        tf.text = "Generated by MODYFIRE"
        p = tf.paragraphs[0]
        p.font.size = Pt(32)
        p.font.bold = True
        p.font.color.rgb = title_rgb
        p.alignment = 2 # CENTER

    output = io.BytesIO()
    prs.save(output)
    output.seek(0)
    return output.read()
