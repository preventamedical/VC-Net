import torch
import logging
import numpy as np
from torch.autograd import Variable
from utils.metrics import metrics_test_drive_all, metrics_test_drive_dice
from utils.utils import adjust_learning_rate, print_writer_scalar

def model_train(cfg, Net, train_loader, criterion, criterion1, optimizer, epoch):

    loss_sigma = []  # 记录一个epoch的loss之和
    Net.train()
    for step, data in enumerate(train_loader):
        _ = adjust_learning_rate(optimizer,
                                  cfg.lr,
                                  cfg.max_epoch * cfg.data_size/cfg.batchsize,
                                  epoch * cfg.data_size/cfg.batchsize + step)
        # 获取图片和标签
        image, label_av_, label_v_, _ = data
        inputs = Variable(image.cuda())
        label_av = Variable(label_av_.cuda().type(torch.long))
        label_v = Variable(label_v_.cuda().type(torch.long))
        # https://blog.csdn.net/VictoriaW/article/details/72673110
        # ================================ ##        优化
        optimizer.zero_grad()
        outputs, vessel = Net(inputs)
        loss_av = criterion(outputs, label_av)
        loss_v = criterion1(vessel.squeeze(), label_v.float())
        # loss = loss_av
        loss = 0.6 * loss_av + 0.4 * loss_v
        loss.backward()
        optimizer.step()
        # 指标计算
        loss_sigma.append(loss_av.item())
    # # ================================ ##        相关结果指标显示及记录
    print_writer_scalar(cfg.writer, cfg.logging, {'loss': np.mean(loss_sigma)}, epoch, 'train')
    # ================================ ##        更新writer缓存区
    cfg.writer.flush()


def model_validate(cfg, Net, validate_loader, epoch):
    F1AV = []; SE_AV = []; SP_AV = []; BA_AV = []; SE_V = []; SP_V = []; A_V = []; AUC = []; F1 = []
    with torch.no_grad():
        for step, data in enumerate(validate_loader):
            # 获取图片和标签
            image1, label_av_, label_v_, mask = data

            inputs = Variable(image1.cuda())
            outputs, ves = Net(inputs)

            outputs = torch.softmax(outputs, 1)
            _, predict_av = torch.max(outputs.cpu().data, 1)

            _, f1av, seav, spav, bacc, se, sp, acc, auc, f1 = \
                metrics_test_drive_all(predict_av.squeeze(), label_av_.squeeze(),
                                   ves.cpu().squeeze(), label_v_.squeeze(),
                                   mask.squeeze(), [2, 3])

            F1AV.append(f1av); SE_AV.append(seav); SP_AV.append(spav);BA_AV.append(bacc)
            SE_V.append(se);SP_V.append(sp);A_V.append(acc);AUC.append(auc);F1.append(f1)
    # ================================ ##        相关结果指标显示及记录
    mean_accuracy_v = np.mean(np.mean(np.stack(F1AV)[:, 1]))
    dict_message_test = {
        'Dice_v': np.mean(np.stack(F1AV)[:, 0]),
        'Dice_a': np.mean(np.stack(F1AV)[:, 1]),
        'BA_AV': np.mean(BA_AV), 'SE_AV': np.mean(SE_AV), 'SP_AV': np.mean(SP_AV),
        'A_V': np.mean(A_V), 'SE_V': np.mean(SE_V), 'SP_V': np.mean(SP_V),
        'AUC': np.mean(AUC), 'Dice_V': np.mean(F1),
    }
    print_writer_scalar(cfg.writer, logging, dict_message_test, epoch, 'test')
    # ================================ ##        更新writer缓存区
    cfg.writer.flush()

    return mean_accuracy_v

from utils.data_utils import get_test_patches, recompone_overlap
def model_validate_patch(cfg, Net, validate_loader, epoch):
    F1AV = []
    with torch.no_grad():
        for step, data in enumerate(validate_loader):
            # 获取图片和标签
            image1, _, label_av_, label_v_, basename = data
            patches_pred, old_size, new_size = get_test_patches(image1, 256, 128)
            inputs = Variable(patches_pred.cuda())
            cnt = len(inputs)
            outputs = []
            for i in range(cnt):
                output, _ = Net(inputs[i:i + 1])
                # macs, params = profile(Net, inputs=(inputs[i:i+1],))
                outputs.append(output)
            outputs = torch.softmax(torch.stack(outputs).squeeze(), 1)
            pred_imgs = recompone_overlap(outputs.cpu().data, 256, 128, new_size, new_size)
            pred_imgs = pred_imgs[:, :, 0:old_size, 0:old_size]
            _, predict_av = torch.max(pred_imgs, 1)
            # _, predict_av = torch.max(outputs.cpu().data, 1)

            f1av = metrics_test_drive_all(predict_av.squeeze(), label_av_.squeeze(), [2, 1])
            F1AV.append(f1av)
    # ================================ ##        相关结果指标显示及记录
    mean_accuracy_v = np.mean(np.mean(np.stack(F1AV)[:, 1]))
    dict_message_test = {
        'Dice_a': np.mean(np.stack(F1AV)[:, 0]),
        'Dice_v': np.mean(np.stack(F1AV)[:, 1]),
    }
    print_writer_scalar(cfg.writer, logging, dict_message_test, epoch, 'test')
    # ================================ ##        更新writer缓存区
    cfg.writer.flush()

    return mean_accuracy_v
