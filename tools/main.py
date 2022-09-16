# encoding: utf-8

import os
import sys
import torch
from torch.backends import cudnn
sys.path.append('.')
from config import cfg
from data import make_data_loader
from modeling import build_model
from utils.lr_scheduler import WarmupMultiStepLR
from utils.logger import setup_logger
from tools.train import do_train
from tools.test import do_test
# import argparse


def main(config_file, opts):
    """
    # config_file: path to config file
    # opts: modify config options using the command-line
    # config_file, opts = None
    parser = argparse.ArgumentParser(description="AGW Re-ID Baseline")
    parser.add_argument(
        "--config_file", default="", help="path to config file", type=str
    )
    parser.add_argument("opts",
                        help="Modify config options using the command-line",
                        default=None,
                        nargs=argparse.REMAINDER)

    args = parser.parse_args()
    """
    # 通过 os.environ 可以获取环境变量
    print("WORLD_SIZE" if "WORLD_SIZE" in os.environ else 1)
    num_gpus = int(
        os.environ["WORLD_SIZE"]) if "WORLD_SIZE" in os.environ else 1

    if config_file != "":
        cfg.merge_from_file(config_file)
    cfg.merge_from_list(opts)
    cfg.freeze()

    output_dir = cfg.OUTPUT_DIR
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    logger = setup_logger("reid_baseline", output_dir, 0)
    logger.info("Using {} GPUS".format(num_gpus))
    # logger.info(args)

    if config_file != "":
        logger.info("Loaded configuration file {}".format(config_file))
        with open(config_file, 'r') as cf:
            config_str = "\n" + cf.read()
            logger.info(config_str)
    logger.info("Running with config:\n{}".format(cfg))

    if cfg.MODEL.DEVICE == "cuda":
        os.environ[
            'CUDA_VISIBLE_DEVICES'] = cfg.MODEL.DEVICE_ID  # new add by gu
    cudnn.benchmark = True

    data_loader, num_query, num_classes = make_data_loader(cfg)
    model = build_model(cfg, num_classes)

    if 'cpu' not in cfg.MODEL.DEVICE:
        if torch.cuda.device_count() > 1:
            model = torch.nn.DataParallel(model)
        model.to(device=cfg.MODEL.DEVICE)

    if cfg.TEST.EVALUATE_ONLY == 'on':
        logger.info("Evaluate Only")
        model.load_param(cfg.TEST.WEIGHT)
        do_test(cfg, model, data_loader, num_query)
        return

    criterion = model.get_creterion(cfg, num_classes)
    optimizer = model.get_optimizer(cfg, criterion)

    # Add for using self trained model
    if cfg.MODEL.PRETRAIN_CHOICE == 'self':
        start_epoch = eval(
            cfg.MODEL.PRETRAIN_PATH.split('/')[-1].split('.')[0].split('_')[-1])
        print('Start epoch:', start_epoch)
        path_to_optimizer = cfg.MODEL.PRETRAIN_PATH.replace('model',
                                                            'optimizer')
        print('Path to the checkpoint of optimizer:', path_to_optimizer)
        path_to_center_param = cfg.MODEL.PRETRAIN_PATH.replace('model',
                                                               'center_param')
        print('Path to the checkpoint of center_param:', path_to_center_param)
        path_to_optimizer_center = cfg.MODEL.PRETRAIN_PATH.replace('model',
                                                                   'optimizer_center')
        print('Path to the checkpoint of optimizer_center:',
              path_to_optimizer_center)
        model.load_state_dict(torch.load(cfg.MODEL.PRETRAIN_PATH))
        optimizer['model'].load_state_dict(torch.load(path_to_optimizer))
        criterion['center'].load_state_dict(torch.load(path_to_center_param))
        optimizer['center'].load_state_dict(
            torch.load(path_to_optimizer_center))
        scheduler = WarmupMultiStepLR(optimizer['model'], cfg.SOLVER.STEPS,
                                      cfg.SOLVER.GAMMA,
                                      cfg.SOLVER.WARMUP_FACTOR,
                                      cfg.SOLVER.WARMUP_ITERS,
                                      cfg.SOLVER.WARMUP_METHOD, start_epoch)
    elif cfg.MODEL.PRETRAIN_CHOICE == 'imagenet':
        start_epoch = 0
        scheduler = WarmupMultiStepLR(optimizer['model'], cfg.SOLVER.STEPS,
                                      cfg.SOLVER.GAMMA,
                                      cfg.SOLVER.WARMUP_FACTOR,
                                      cfg.SOLVER.WARMUP_ITERS,
                                      cfg.SOLVER.WARMUP_METHOD)
    else:
        print(
            'Only support pretrain_choice for imagenet and self, but got {}'.format(
                cfg.MODEL.PRETRAIN_CHOICE))

    do_train(cfg,
             model,
             data_loader,
             optimizer,
             scheduler,
             criterion,
             num_query,
             start_epoch
             )


if __name__ == '__main__':
    config_file = '../configs/AGW_baseline.yml'
    opts = ['MODEL.DEVICE_ID', "('0')",
            'DATASETS.NAMES', "('market1501')",
            'OUTPUT_DIR', "('./log/market1501/Experiment-AGW-baseline')",
            'MODEL.PRETRAIN_PATH', "('/media/server/Files/Model/Janson/ReID-AGW/Pre-train/resnet50-19c8e357.pth')",
            'SOLVER.CHECKPOINT_PERIOD', '(50)']

    main(config_file, opts)
