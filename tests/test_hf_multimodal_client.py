"""Exercise processor-based text generation without downloading GPU weights."""
import contextlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from colorref.llm_clients import HFTransformersClient, build_client


class Inputs(dict):
    def __init__(self):
        self.input_ids = SimpleNamespace(shape=(1, 3))
        super().__init__(input_ids=self.input_ids)

    def to(self, device):
        self.device = device
        return self


class MultimodalTests(unittest.TestCase):
    def test_processor_path_and_output_only_tokens(self):
        model = Mock(device="cuda:0", generation_config=SimpleNamespace(eos_token_id=9))
        model.generate.return_value = [[1, 2, 3, 4, 9]]
        processor = Mock()
        processor.apply_chat_template.return_value = Inputs()
        processor.decode.return_value = "LAB(50, 1, 2)"
        classes = SimpleNamespace(
            AutoModelForCausalLM=Mock(), AutoTokenizer=Mock(),
            AutoModelForMultimodalLM=Mock(), AutoProcessor=Mock(),
        )
        classes.AutoModelForMultimodalLM.from_pretrained.return_value = model
        classes.AutoProcessor.from_pretrained.return_value = processor
        torch = SimpleNamespace(bfloat16="bf16", float16="fp16", float32="fp32", no_grad=contextlib.nullcontext)
        with patch.dict(sys.modules, transformers=classes, torch=torch):
            client = build_client({"model_name": "gemma-fixture", "revision": "pinned", "model_loader": "multimodal"})
            response = client.generate("unchanged instruction", max_tokens=64, temperature=0)
        self.assertEqual(response.text, "LAB(50, 1, 2)")
        self.assertEqual(response.raw["generated_tokens"], 2)
        self.assertEqual(response.raw["prompt_tokens"], 3)
        self.assertTrue(response.raw["eos_reached"])
        classes.AutoModelForCausalLM.from_pretrained.assert_not_called()
        classes.AutoProcessor.from_pretrained.assert_called_once_with("gemma-fixture", revision="pinned")
        self.assertEqual(classes.AutoModelForMultimodalLM.from_pretrained.call_args.kwargs["revision"], "pinned")
        processor.apply_chat_template.assert_called_once_with(
            [{"role": "user", "content": "unchanged instruction"}], tokenize=True,
            return_dict=True, return_tensors="pt", add_generation_prompt=True, enable_thinking=False,
        )
        processor.decode.assert_called_once_with([4, 9], skip_special_tokens=True)
        model.generate.assert_called_once_with(input_ids=processor.apply_chat_template.return_value.input_ids, max_new_tokens=64, do_sample=False)

    def test_unknown_loader_fails_before_loading(self):
        with self.assertRaises(ValueError):
            HFTransformersClient("fixture", model_loader="invalid")

    def test_default_keeps_qwen_loader(self):
        with patch.object(HFTransformersClient, "_load_model", return_value=(None, None)):
            self.assertEqual(build_client({"model_name": "Qwen/Qwen3-14B"}).model_loader, "causal")


if __name__ == "__main__":
    unittest.main()
