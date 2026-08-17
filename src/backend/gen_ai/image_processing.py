import os

try:
    from PIL import Image
except ModuleNotFoundError:
    Image = None

try:
    import google.genai as genai
except ModuleNotFoundError:
    genai = None


_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

def _get_genai_client():
    if genai is None:
        raise RuntimeError(
            "google-genai is not installed. Install it with: pip install google-genai"
        )
    api_key = _GEMINI_API_KEY
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Please export it before calling extract_text()."
        )
    return genai.Client(api_key=api_key, http_options={"api_version": "v1"})


def extract_text(image_path):
    if Image is None:
        print("Pillow not installed; skipping image text extraction.")
        return None

    try:
        img = Image.open(image_path)
        prompt = (
            "Describe the civic issue in the given image (i.e. pothole, garbage, broken light). "
            "Provide details like severity and surroundings."
        )
        try:
            client = _get_genai_client()
        except RuntimeError as exc:
            print(f"Image description skipped: {exc}")
            return None

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, img],
        )
        print(response)
        return response.text
    except FileNotFoundError:
        print(f"Error: The file at {image_path} was not found.")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


# extract_text("face.jpeg")
