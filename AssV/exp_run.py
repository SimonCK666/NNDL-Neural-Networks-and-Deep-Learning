'''
Author: SimonCK666 SimonYang223@163.com
Date: 2022-11-21 16:07:14
LastEditors: SimonCK666 SimonYang223@163.com
LastEditTime: 2022-11-21 16:37:35
FilePath: /AssV/exp_run.py
Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
'''
import keras
print(keras.__version__)

from keras.preprocessing.image import load_img, img_to_array

import numpy as np
from keras.applications import vgg19

'''
显示所有可用设备
'''
from tensorflow.python.client import device_lib
print(device_lib.list_local_devices())

'''
指定一个不存在的gpu（切换回cpu）
'''
# import os
# os.environ["CUDA_VISIBLE_DEVICES"] = "-1" 

'''
指定一个可用gpu
'''
# import os
# os.environ["CUDA_VISIBLE_DEVICES"] = "0"

'''
指定多个可用gpu
'''
# import os
# os.environ["CUDA_VISIBLE_DEVICES"] = "1,0"

'''
配置
tf.ConfigProto一般用在创建session的时候，用来对session进行参数配置，
而tf.GPUOptions可以作为设置tf.ConfigProto时的一个参数选项，一般用于限制GPU资源的使用。

作者：Byte猫
链接：https://www.jianshu.com/p/e772b880b4d2
来源：简书
著作权归作者所有。商业转载请联系作者获得授权，非商业转载请注明出处。
'''
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"  # 使用'/gpu:0'

import tensorflow as tf
import keras.backend.tensorflow_backend as KTF

# GPU资源配置
config = tf.ConfigProto(log_device_placement=False)
config.gpu_options.per_process_gpu_memory_fraction = 0.9 # 每个GPU现存上届控制在90%以内
# session的参数配置
session = tf.Session(config=config)
# 应用session配置
KTF.set_session(session)


#=====================================================================
#=====================================================================


'''
Let's start by defining the paths to the two images we consider: 
the style reference image and the target image. 
To make sure that all images processed share similar sizes 
(widely different sizes would make style transfer more difficult), 
we will later resize them all to a shared height of 400px.
'''
# This is the path to the image you want to transform.
# target_image_path = '/home/ubuntu/data/portrait.png'
target_image_path = 'GoldenGate.jpeg'

# This is the path to the style image.
# style_reference_image_path = '/home/ubuntu/data/popova.jpg'
style_reference_image_path = 'VanGaugh.jpeg'


# Dimensions of the generated picture.
width, height = load_img(target_image_path).size
img_height = 400
img_width = int(width * img_height / height)

'''
We will need some auxiliary functions for loading, 
pre-processing and post-processing the images that will go in and out of the VGG19 convnet:
'''
# We will need some auxiliary functions for loading, pre-processing and post-processing the images that will go in and out of the VGG19 convnet:
def preprocess_image(image_path):
    img = load_img(image_path, target_size=(img_height, img_width))
    img = img_to_array(img)
    img = np.expand_dims(img, axis=0)
    img = vgg19.preprocess_input(img)
    return img

def deprocess_image(x):
    # Remove zero-center by mean pixel
    x[:, :, 0] += 103.939
    x[:, :, 1] += 116.779
    x[:, :, 2] += 123.68
    # 'BGR'->'RGB'
    x = x[:, :, ::-1]
    x = np.clip(x, 0, 255).astype('uint8')
    return x

'''
Let's set up the VGG19 network. It takes as input a batch of three images: 
the style reference image, the target image, and a placeholder that will contain the generated image. 
A placeholder is simply a symbolic tensor, the values of which are provided externally via Numpy arrays. 
The style reference and target image are static, and thus defined using K.constant, 
while the values contained in the placeholder of the generated image will change over time.
'''
from keras import backend as K

target_image = K.constant(preprocess_image(target_image_path))
style_reference_image = K.constant(preprocess_image(style_reference_image_path))

# This placeholder will contain our generated image
combination_image = K.placeholder((1, img_height, img_width, 3))

# We combine the 3 images into a single batch
input_tensor = K.concatenate([target_image,
                              style_reference_image,
                              combination_image], axis=0)

# We build the VGG19 network with our batch of 3 images as input.
# The model will be loaded with pre-trained ImageNet weights.
model = vgg19.VGG19(input_tensor=input_tensor,
                    weights='imagenet',
                    include_top=False)
print('Model loaded.')

'''
Let's define the content loss, meant to make sure that the top layer of the VGG19 
convnet will have a similar view of the target image and the generated image:
'''
def content_loss(base, combination):
    return K.sum(K.square(combination - base))

'''
Now, here's the style loss. It leverages an auxiliary function to compute the Gram matrix of an input matrix, 
i.e. a map of the correlations found in the original feature matrix.
'''
def gram_matrix(x):
    features = K.batch_flatten(K.permute_dimensions(x, (2, 0, 1)))
    gram = K.dot(features, K.transpose(features))
    return gram


def style_loss(style, combination):
    S = gram_matrix(style)
    C = gram_matrix(combination)
    channels = 3
    size = img_height * img_width
    return K.sum(K.square(S - C)) / (4. * (channels ** 2) * (size ** 2))

'''
To these two loss components, we add a third one, the "total variation loss". 
It is meant to encourage spatial continuity in the generated image, 
thus avoiding overly pixelated results. You could interpret it as a regularization loss
'''
def total_variation_loss(x):
    a = K.square(
        x[:, :img_height - 1, :img_width - 1, :] - x[:, 1:, :img_width - 1, :])
    b = K.square(
        x[:, :img_height - 1, :img_width - 1, :] - x[:, :img_height - 1, 1:, :])
    return K.sum(K.pow(a + b, 1.25))

'''
The loss that we minimize is a weighted average of these three losses. 
To compute the content loss, we only leverage one top layer, the block5_conv2 layer, 
while for the style loss we use a list of layers than spans both low-level and high-level layers. 
We add the total variation loss at the end.

Depending on the style reference image and content image you are using, 
you will likely want to tune the content_weight coefficient, 
the contribution of the content loss to the total loss. 
A higher content_weight means that the target content will be more recognizable in the generated image.
'''
# Dict mapping layer names to activation tensors
outputs_dict = dict([(layer.name, layer.output) for layer in model.layers])
# Name of layer used for content loss
content_layer = 'block5_conv2'
# Name of layers used for style loss
style_layers = ['block1_conv1',
                'block2_conv1',
                'block3_conv1',
                'block4_conv1',
                'block5_conv1']
# Weights in the weighted average of the loss components
total_variation_weight = 1e-4
style_weight = 1.
content_weight = 0.025

# Define the loss by adding all components to a `loss` variable
loss = K.variable(0.)
layer_features = outputs_dict[content_layer]
target_image_features = layer_features[0, :, :, :]
combination_features = layer_features[2, :, :, :]
loss += content_weight * content_loss(target_image_features,
                                      combination_features)
for layer_name in style_layers:
    layer_features = outputs_dict[layer_name]
    style_reference_features = layer_features[1, :, :, :]
    combination_features = layer_features[2, :, :, :]
    sl = style_loss(style_reference_features, combination_features)
    loss += (style_weight / len(style_layers)) * sl
loss += total_variation_weight * total_variation_loss(combination_image)

'''
It would be very inefficient for us to compute the value of the loss function and the value of 
gradients independently, since it would lead to a lot of redundant computation between the two. 
We would be almost twice slower than we could be by computing them jointly. 
To by-pass this, we set up a Python class named Evaluator that will compute both loss value and 
gradients value at once, will return the loss value when called the first time, 
and will cache the gradients for the next call.
'''
# Get the gradients of the generated image wrt the loss
grads = K.gradients(loss, combination_image)[0]

# Function to fetch the values of the current loss and the current gradients
fetch_loss_and_grads = K.function([combination_image], [loss, grads])


class Evaluator(object):

    def __init__(self):
        self.loss_value = None
        self.grads_values = None

    def loss(self, x):
        assert self.loss_value is None
        x = x.reshape((1, img_height, img_width, 3))
        outs = fetch_loss_and_grads([x])
        loss_value = outs[0]
        grad_values = outs[1].flatten().astype('float64')
        self.loss_value = loss_value
        self.grad_values = grad_values
        return self.loss_value

    def grads(self, x):
        assert self.loss_value is not None
        grad_values = np.copy(self.grad_values)
        self.loss_value = None
        self.grad_values = None
        return grad_values

evaluator = Evaluator()

'''
Finally, we can run the gradient ascent process using SciPy's L-BFGS algorithm, 
saving the current generated image at each iteration of the algorithm 
(here, a single iteration represents 20 steps of gradient ascent):
'''
from scipy.optimize import fmin_l_bfgs_b
from scipy.misc import imsave
import time

result_prefix = 'style_transfer_result'
iterations = 20

# Run scipy-based optimization (L-BFGS) over the pixels of the generated image
# so as to minimize the neural style loss.
# This is our initial state: the target image.
# Note that `scipy.optimize.fmin_l_bfgs_b` can only process flat vectors.
x = preprocess_image(target_image_path)
x = x.flatten()
for i in range(iterations):
    print('Start of iteration', i)
    start_time = time.time()
    x, min_val, info = fmin_l_bfgs_b(evaluator.loss, x,
                                     fprime=evaluator.grads, maxfun=20)
    print('Current loss value:', min_val)
    # Save current generated image
    img = x.copy().reshape((img_height, img_width, 3))
    img = deprocess_image(img)
    fname = result_prefix + '_at_iteration_%d.png' % i
    imsave(fname, img)
    end_time = time.time()
    print('Image saved as', fname)
    print('Iteration %d completed in %ds' % (i, end_time - start_time))
    
'''
Here's what we get:
'''
from matplotlib import pyplot as plt

# Content image
plt.imshow(load_img(target_image_path, target_size=(img_height, img_width)))
plt.figure()

# Style image
plt.imshow(load_img(style_reference_image_path, target_size=(img_height, img_width)))
plt.figure()

# Generate image
plt.imshow(img)
plt.show()