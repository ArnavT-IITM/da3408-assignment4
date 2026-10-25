from pathlib import Path
from threading import Lock

import torch
from transformers import BlipForConditionalGeneration, BlipProcessor


class Captioner:
    def __init__(self):
        path = Path(__file__).parent / "model"
        torch.set_num_threads(4)
        self.processor = BlipProcessor.from_pretrained(path, local_files_only=True)
        self.model = BlipForConditionalGeneration.from_pretrained(
            path, local_files_only=True
        ).to("cpu").eval()
        self.lock = Lock()

    def caption(self, image):
        with self.lock, torch.inference_mode():
            inputs = self.processor(images=image.convert("RGB"), return_tensors="pt")
            output = self.model.generate(**inputs, max_new_tokens=40, do_sample=False)
        return self.processor.decode(output[0], skip_special_tokens=True)
