from collections import OrderedDict

import torch
import torch.nn as nn

from modules import *


__all__ = ['resnet12', 'wide_resnet12']



models = {}
def register(name):
  def decorator(cls):
    models[name] = cls
    return cls
  return decorator


def conv3x3(in_channels, out_channels):
  return Conv2d(in_channels, out_channels, 3, 1, padding=1, bias=False)


def conv1x1(in_channels, out_channels):
  return Conv2d(in_channels, out_channels, 1, 1, padding=0, bias=False)


class Block(Module):
  def __init__(self, in_planes, planes, bn_args):
    super(Block, self).__init__()
    self.in_planes = in_planes
    self.planes = planes

    self.conv1 = conv3x3(in_planes, planes)
    self.bn1 = BatchNorm2d(planes, **bn_args)
    self.conv2 = conv3x3(planes, planes)
    self.bn2 = BatchNorm2d(planes, **bn_args)
    self.conv3 = conv3x3(planes, planes)
    self.bn3 = BatchNorm2d(planes, **bn_args)

    self.res_conv = Sequential(OrderedDict([
      ('conv', conv1x1(in_planes, planes)),
      ('bn', BatchNorm2d(planes, **bn_args)),
    ]))

    self.relu = nn.LeakyReLU(0.1, inplace=True)
    self.pool = nn.MaxPool2d(2)

  def forward(self, x, params=None, episode=None):
    out = self.conv1(x, get_child_dict(params, 'conv1'))
    out = self.bn1(out, get_child_dict(params, 'bn1'), episode)
    out = self.relu(out)

    out = self.conv2(out, get_child_dict(params, 'conv2'))
    out = self.bn2(out, get_child_dict(params, 'bn2'), episode)
    out = self.relu(out)

    out = self.conv3(out, get_child_dict(params, 'conv3'))
    out = self.bn3(out, get_child_dict(params, 'bn3'), episode)

    x = self.res_conv(x, get_child_dict(params, 'res_conv'), episode)
    out = self.pool(self.relu(out + x))
    return out


class ResNet12(Module):
  def __init__(self, channels, bn_args, normalize=True):
    super(ResNet12, self).__init__()
    self.channels = channels

    episodic = bn_args.get('episodic') or []
    bn_args_ep, bn_args_no_ep = bn_args.copy(), bn_args.copy()
    bn_args_ep['episodic'] = True
    bn_args_no_ep['episodic'] = False
    bn_args_dict = dict()
    for i in [1, 2, 3, 4]:
      if 'layer%d' % i in episodic:
        bn_args_dict[i] = bn_args_ep
      else:
        bn_args_dict[i] = bn_args_no_ep

    self.layer1 = Block(1, channels[0], bn_args_dict[1])
    self.layer2 = Block(channels[0], channels[1], bn_args_dict[2])
    self.layer3 = Block(channels[1], channels[2], bn_args_dict[3])
    self.layer4 = Block(channels[2], channels[3], bn_args_dict[4])
    
    self.pool = nn.AdaptiveAvgPool2d(1)
    self.out_dim = channels[3]

    if normalize:
      self.l2_norm = L2_norm()
    else:
      self.l2_norm = nn.Identity()

    for m in self.modules():
      if isinstance(m, Conv2d):
        nn.init.kaiming_normal_(
          m.weight, mode='fan_out', nonlinearity='leaky_relu')
      elif isinstance(m, BatchNorm2d):
        nn.init.constant_(m.weight, 1.)
        nn.init.constant_(m.bias, 0.)

  def get_out_dim(self):
    return self.out_dim

  def forward(self, x, params=None, episode=None):
    out = self.layer1(x, get_child_dict(params, 'layer1'), episode)
    out = self.layer2(out, get_child_dict(params, 'layer2'), episode)
    out = self.layer3(out, get_child_dict(params, 'layer3'), episode)
    out = self.layer4(out, get_child_dict(params, 'layer4'), episode)
    out = self.pool(out).flatten(1)

    return self.l2_norm(out)


@register('resnet12')
def resnet12(bn_args=dict(), normalize=True):
  return ResNet12([64, 128, 256, 512], bn_args, normalize=normalize)


@register('wide-resnet12')
def wide_resnet12(bn_args=dict(), normalize=True):
  return ResNet12([64, 160, 320, 640], bn_args, normalize=normalize)