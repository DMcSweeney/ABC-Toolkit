
import os
import json
import copy
import torch
import logging
from typing import Dict


import monailabel
from monailabel.config import settings

from monailabel.interfaces.app import MONAILabelApp
from monailabel.utils.others.generic import get_bundle_models, strtobool
from monailabel.utils.others.planner import HeuristicPlanner
from monailabel.interfaces.datastore import Datastore, DefaultLabelTag
from monailabel.interfaces.config import TaskConfig
from monailabel.interfaces.tasks.infer_v2 import InferTask
from monailabel.utils.others.class_utils import get_class_names
from monailabel.tasks.infer.bundle import BundleInferTask
from monailabel.interfaces.exception import MONAILabelError, MONAILabelException
from monailabel.utils.others.generic import file_ext, device_list, handle_torch_linalg_multithread


import abcTK.spine.configs
from abcTK.spine.engines.vertebra_pipeline import InferVertebraPipeline

logger = logging.getLogger(__name__)

class spineApp(MONAILabelApp):
    def __init__(self, app_dir, studies, conf):

        
        self.model_dir = os.path.join(app_dir, "model")
        
        configs = {}
        for c in get_class_names(abcTK.spine.configs, "TaskConfig"):
            name = c.split(".")[-2].lower()
            configs[name] = c

        configs = {k: v for k, v in sorted(configs.items())}
        
        # Load models from app model implementation, e.g., --conf models <segmentation_spleen>
        models = conf.get("models")
        models = models.split(",")
        models = [m.strip() for m in models]
        
        # Use Heuristic Planner to determine target spacing and spatial size based on dataset+gpu
        spatial_size = json.loads(conf.get("spatial_size", "[48, 48, 32]"))
        target_spacing = json.loads(conf.get("target_spacing", "[1.0, 1.0, 1.0]"))
        self.heuristic_planner = strtobool(conf.get("heuristic_planner", "false"))
        self.planner = HeuristicPlanner(spatial_size=spatial_size, target_spacing=target_spacing)

        # app models
        self.models: Dict[str, TaskConfig] = {}
        for n in models:
            for k, v in configs.items():
                if self.models.get(k):
                    continue
                if n == k or n == "all":
                    logger.info(f"+++ Adding Model: {k} => {v}")
                    self.models[k] = eval(f"{v}()")
                    self.models[k].init(k, self.model_dir, conf, self.planner)
                
        logger.info(f"+++ Using Models: {list(self.models.keys())}")
        
        self._infers = self.init_infers()

        # Load models from bundle config files, local or released in Model-Zoo, e.g., --conf bundles <spleen_ct_segmentation>
        #self.bundles = get_bundle_models(app_dir, conf, conf_key="bundles") if conf.get("bundles") else None

        # super().__init__(
        #     app_dir=app_dir,
        #     studies=studies,
        #     conf=conf,
        #     name=f"Spine Labelling ",
        #     description="App for doing spine labelling",
        #     version=monailabel.__version__,
        # )

    def init_infers(self) -> Dict[str, InferTask]:
        infers: Dict[str, InferTask] = {}

        #################################################
        # Models
        #################################################
        for n, task_config in self.models.items():
            c = task_config.infer()
            c = c if isinstance(c, dict) else {n: c}
            for k, v in c.items():
                logger.info(f"+++ Adding Inferer:: {k} => {v}")
                infers[k] = v

        #################################################
        # Bundle Models
        #################################################
        # if self.bundles:
        #     for n, b in self.bundles.items():
        #         i = BundleInferTask(b, self.conf)
        #         logger.info(f"+++ Adding Bundle Inferer:: {n} => {i}")
        #         infers[n] = i

        #################################################
        # Pipeline based on existing infers for vertebra segmentation
        # Stages:
        # 1/ localization spine
        # 2/ localization vertebra
        # 3/ segmentation vertebra
        #################################################
        if (
            infers.get("find_spine")
            and infers.get("find_vertebra")
            and infers.get("segment_vertebra")
        ):
            logger.info("--- VERTEBRA PIPELINE ACTIVE ---")
            infers["vertebra_pipeline"] = InferVertebraPipeline(
                task_loc_spine=infers["find_spine"],  # first stage
                task_loc_vertebra=infers["find_vertebra"],  # second stage
                task_seg_vertebra=infers["segment_vertebra"],  # third stage
                description="Combines three stage for vertebra segmentation",
            )

        
        return infers
    
    def infer(self, request, datastore=None):
        """
        Run Inference for an exiting pre-trained model.

        Args:
            request: JSON object which contains `model`, `image`, `params` and `device`
            datastore: Datastore object.  If None then use default app level datastore to save labels if applicable

                For example::

                    {
                        "device": "cuda"
                        "model": "segmentation_spleen",
                        "image": "file://xyz",
                        "save_label": "true/false",
                        "label_tag": "original"
                    }

        Raises:
            MONAILabelException: When ``model`` is not found

        Returns:
            JSON containing `label` and `params`
        """
        model = request.get("model")
        if not model:
            raise MONAILabelException(
                MONAILabelError.INVALID_INPUT,
                "Model is not provided for Inference Task",
            )

        task = self._infers.get(model)
    
        if not task:
            raise MONAILabelException(
                MONAILabelError.INVALID_INPUT,
                f"Inference Task is not Initialized. There is no model '{model}' available",
            )

        request = copy.deepcopy(request)
        request["description"] = task.description

        image_id = request["image"]
        if isinstance(image_id, str):
            #datastore = datastore if datastore else self.datastore()
            if os.path.exists(image_id):
                request["save_label"] = False
            else:
                raise ValueError(f"Path does not exist: {image_id}")
                #request["image"] = datastore.get_image_uri(request["image"])

            if os.path.isdir(request["image"]):
                logger.info("Input is a Directory; Consider it as DICOM")

            logger.debug(f"Image => {request['image']}")
        else:
            request["save_label"] = False

        result_file_name, result_json = task(request)
        
        label_id = None
        if isinstance(result_file_name, str) and os.path.exists(result_file_name):
        #if result_file_name and os.path.exists(result_file_name):
            label_id = result_file_name
        else:
            logger.info("No filename specified, returning numpy array with prediction")

        return {"label": label_id, "tag": DefaultLabelTag.ORIGINAL, "file": result_file_name, "params": result_json}

