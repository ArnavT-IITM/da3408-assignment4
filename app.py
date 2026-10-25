from time import perf_counter
from uuid import uuid4
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from PIL import Image, ImageOps
import streamlit as st

from captioner import Captioner
from metrics import Metrics


@st.cache_resource
def load_captioner():
    return Captioner()


@st.cache_resource
def load_metrics():
    metrics = Metrics()
    metrics.start()
    return metrics


metrics = load_metrics()
if "session_id" not in st.session_state:
    st.session_state.session_id = uuid4().hex
session = st.session_state.session_id
for metric_mode in ("single", "bulk"):
    for outcome in ("success", "failure"):
        metrics.images.labels(metric_mode, session, outcome)


def process_image(source, mode):
    with metrics.image(mode, session):
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
        caption = load_captioner().caption(image)
    return image, caption


st.set_page_config(page_title="Image captioning")
st.title("Image captioning")
mode = st.radio("Mode", ["Single", "Bulk"], horizontal=True)

if mode == "Bulk":
    st.write("Upload a ZIP of JPG, PNG or WebP images. Images are processed one at a time.")
    upload = st.file_uploader("Choose a ZIP", type=["zip"], key="bulk")
    if upload is not None:
        try:
            archive = ZipFile(upload)
        except BadZipFile:
            st.error("This file could not be opened as a ZIP archive.")
            st.stop()
        with archive:
            files = [
                item for item in archive.infolist()
                if not item.is_dir()
                and PurePosixPath(item.filename).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
                and not any(part.startswith((".", "__MACOSX")) for part in PurePosixPath(item.filename).parts)
            ]
            if not files:
                st.warning("No supported images were found in this ZIP.")
                st.stop()
            st.write(f"Found {len(files)} images.")
            if st.button("Generate captions", type="primary"):
                with metrics.request("bulk"):
                    with st.spinner("Loading the captioning model..."):
                        load_captioner()
                    metrics.batch_size.observe(len(files))
                    progress = st.progress(0)
                    results = []
                    for index, item in enumerate(files):
                        try:
                            with metrics.image("bulk", session):
                                if item.file_size > 20 * 1024 * 1024:
                                    raise ValueError("Image exceeds the 20 MB per-image limit.")
                                start = perf_counter()
                                with archive.open(item) as source:
                                    data = source.read(20 * 1024 * 1024 + 1)
                                if len(data) > 20 * 1024 * 1024:
                                    raise ValueError("Image exceeds the 20 MB per-image limit.")
                                with Image.open(BytesIO(data)) as source:
                                    image = ImageOps.exif_transpose(source).convert("RGB")
                                caption = load_captioner().caption(image)
                                elapsed = perf_counter() - start
                            results.append({"Image": item.filename, "Caption": caption, "Seconds": round(elapsed, 2)})
                            st.write(f"**{item.filename}**: {caption}")
                        except (OSError, ValueError, RuntimeError, BadZipFile, NotImplementedError, Image.DecompressionBombError) as error:
                            st.warning(f"Skipped {item.filename}: {error}")
                        progress.progress((index + 1) / len(files))
                    st.success(f"Captioned {len(results)} of {len(files)} images.")
                    if results:
                        st.dataframe(results, hide_index=True)
    st.stop()

st.write("Upload an image to generate a caption.")
upload = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png", "webp"], key="single")

if upload is not None:
    if st.button("Generate caption", type="primary"):
        try:
            with metrics.request("single"):
                with st.spinner("Loading the captioning model..."):
                    load_captioner()
                with st.spinner("Generating caption..."):
                    start = perf_counter()
                    image, caption = process_image(upload, "single")
                    elapsed = perf_counter() - start
            st.image(image, width="stretch")
            st.subheader("Caption")
            st.write(caption)
            st.caption(f"Generated in {elapsed:.2f} seconds.")
        except (OSError, ValueError, RuntimeError, Image.DecompressionBombError) as error:
            st.error(f"Could not caption this image: {error}")
