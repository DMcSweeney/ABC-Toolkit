"""
MODEL BANK
"""

model_bank = {
    'C3': {'CT':
            {'path': '/models/segmentation/TitanMixNet-Med-C3-Body-M.onnx',
            'segments': {'background': 0, 'skeletal_muscle': 1, 'body': 2}
            },
        'CBCT':
            {'path': '/models/segmentation/TitanMixNet-Med-CBCT-C3-Body-M.onnx',
            'segments': {'background': 0, 'skeletal_muscle': 1, 'body': 2}
            }
    },
    'T4': {'CT':
            {'path': '/models/segmentation/TitanMixNet-Med-T4-Body-M.onnx',
            'segments': {'background': 0, 'skeletal_muscle': 1, 'body': 2}
            }
    },
    'T9': {'CT':
            {'path': '/models/segmentation/TitanMixNet-Med-T9-Body-M.onnx',
            'segments': {'background': 0, 'skeletal_muscle': 1, 'body': 2}
            }
    },
    'T12': {'CT': {'path': '/models/segmentation/TitanMixNet-Med-T12-Body-M.onnx','segments': {'background': 0, 'skeletal_muscle': 1, 'body': 2}},
            'LowDoseCT': {'path': '/models/segmentation/NLST-T12-M.onnx','segments': {'background': 0, 'skeletal_muscle': 1}}
            },
    'L3': {'CT': 
            {'path': '/models/segmentation/TitanMixNet-Med-L3-FM-with-STAMPEDE-edits.onnx',
            'segments': {'background': 0, 'skeletal_muscle': 1, 'subcutaneous_fat': 2, 'visceral_fat': 3}
            }
    },
    'L5': {'CT': 
            {'path': '/models/segmentation/TitanMixNet-Med-L5-FM.onnx',
            'segments': {'background': 0, 'skeletal_muscle': 1, 'subcutaneous_fat': 2, 'visceral_fat': 3}
            }
    },
    'Sacrum': {'MR': 
                {'path': '/models/segmentation/TitanMixNet-Med-Pelvis-SFM-MRI.onnx',
                    'segments': {'background': 0, 'skeletal_muscle': 1, 'subcutaneous_fat': 2}
                }               
    },
    'Thigh': {'CT':
                {'path': '/models/segmentation/Thigh_14pats.quant.onnx',
                'segments': {'background': 0, 'skeletal_muscle': 1} }
            }
}

