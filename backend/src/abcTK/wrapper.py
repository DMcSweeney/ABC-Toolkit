"""
Wrapper class for serializing ONNX inference session
"""
from onnxruntime import InferenceSession


class ONNXInferenceWrapper(InferenceSession):
    def __init__(self, path, onnx_bytes):
        super().__init__(path)
        self.sess = InferenceSession(onnx_bytes.SerializeToString())
        self.onnx_bytes = onnx_bytes

    def run(self, *args):
        return self.sess.run(*args)

    def __getstate__(self):
        return {'onnx_bytes': self.onnx_bytes}

    def __setstate__(self, values):
        onnx_bytes = values['onnx_bytes']
        self.sess = InferenceSession(onnx_bytes.SerializeToString()) 