## v4 uses two different alphas and image resize upscaling

import tensorflow as tf
import random
import numpy as np
import matplotlib.pyplot as plt
# %matplotlib inline
import pickle
from PIL import Image

BATCH_SIZE = 20  # todo
ITERATIONS = 5000 # todo
D_ALPHA = 3e-6  # the discriminator learning rate todo
G_ALPHA = 3e-4  # the generator learning rate todo

# get the training data
x_train = pickle.load(open('pickled/_0.pickle', "rb"))
# (numImgs, IMAGE_SIZE, IMAGE_SIZE, 1): (###, 512, 512, 1)
IMAGE_SIZE = np.shape(x_train)[1]  # 512
numImgs = np.shape(x_train)[0]

# arrange the images into 1D vectors
x_train = np.array([x_train])
x_train = x_train.reshape([numImgs, IMAGE_SIZE, IMAGE_SIZE, 1])
x_train = x_train / 255 * 2 - 1  # scale between -1 and 1


# if you want to view the original images
# for i in range(10, 14):
#     plt.imshow(x_train[i].reshape([IMAGE_SIZE, IMAGE_SIZE]),
#                cmap=plt.get_cmap('gray'))
#     plt.show()


def conv2d(x, W):
    return tf.nn.conv2d(input=x, filter=W, strides=[1, 1, 1, 1], padding='SAME')


def avg_pool_2x2(x):
    return tf.nn.avg_pool(x, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')


# single x_image is 512*512px
def discriminator(x_image, reuse=False):
    with tf.variable_scope('discriminator') as scope:
        if (reuse):
            tf.get_variable_scope().reuse_variables()
        # First Conv and Pool Layers
        W_conv1 = tf.get_variable(
            'd_wconv1', [5, 5, 1, 8], initializer=tf.truncated_normal_initializer(stddev=0.02))
        b_conv1 = tf.get_variable(
            'd_bconv1', [8], initializer=tf.constant_initializer(0))
        h_conv1 = tf.nn.leaky_relu(conv2d(x_image, W_conv1) + b_conv1)
        # orig h_conv1 dimensions = ; 512 dimensions = 16 512 512 8
        h_pool1 = avg_pool_2x2(h_conv1)

        # Second Conv and Pool Layers
        W_conv2 = tf.get_variable('d_wconv2', [
                                  5, 5, 8, 16], initializer=tf.truncated_normal_initializer(stddev=0.02))
        b_conv2 = tf.get_variable(
            'd_bconv2', [16], initializer=tf.constant_initializer(0))
        h_conv2 = tf.nn.leaky_relu(conv2d(h_pool1, W_conv2) + b_conv2)
        h_pool2 = avg_pool_2x2(h_conv2)

        dimVal = np.shape(h_pool2)[1]*np.shape(h_pool2)[2] * \
            np.shape(h_pool2)[3]  # before: 7 * 7 * 16
        # First Fully Connected Layer
        W_fc1 = tf.get_variable('d_wfc1', [
                                dimVal, 32], initializer=tf.truncated_normal_initializer(stddev=0.02))
        # 7 * 7 * 16, 32], initializer=tf.truncated_normal_initializer(stddev=0.02))
        b_fc1 = tf.get_variable(
            'd_bfc1', [32], initializer=tf.constant_initializer(0))
        # 7*7*16]) # 7*7*16=784
        h_pool2_flat = tf.reshape(h_pool2, [-1, dimVal])
        h_fc1 = tf.nn.leaky_relu(tf.matmul(h_pool2_flat, W_fc1) + b_fc1)

        # Second Fully Connected Layer
        W_fc2 = tf.get_variable(
            'd_wfc2', [32, 1], initializer=tf.truncated_normal_initializer(stddev=0.02))
        b_fc2 = tf.get_variable(
            'd_bfc2', [1], initializer=tf.constant_initializer(0))

        # Final Layer
        y_conv = (tf.matmul(h_fc1, W_fc2) + b_fc2)
    return y_conv


def generator(z, batch_size, z_dim, reuse=False):
    with tf.variable_scope('generator') as scope:
        if (reuse):
            tf.get_variable_scope().reuse_variables()
        g_dim = 64  # Number of filters of first layer of generator
        # Color dimension of output (MNIST is grayscale, so c_dim = 1 for us)
        c_dim = 1
        # s = 28 #Output size of the image
        # Output size of the image --> changed to the number of pixels of our input image (512)
        s = IMAGE_SIZE

        # We want to slowly upscale the image, so these values will help
        s2, s4, s8, s16 = int(s/2), int(s/4), int(s/8), int(s/16)
        # make that change gradual. --> s=512, s2=256, s4=128, s8=64, s16=32

        # h0 = tf.reshape(z, [batch_size, s16+1, s16+1, 25]) # s16 = 128
        # --> s*s/((s16)*(s16)) ---> changed such that s16*s16*256=s*s
        h0 = tf.reshape(z, [batch_size, s16, s16, 256])
        h0 = tf.nn.leaky_relu(h0)
        # Dimensions of h0 = batch_size x 2 x 2 x 25 = 100 --> 1 33 33 25 --> want this to multiply to 512*512

        # First DeConv Layer
        output1_shape = [batch_size, s8, s8, g_dim*4]
        # b_conv and W_conv's are unused --> deleted these
        # instead of tf.nn.conv2d_transpose, let's use resize_images to upsample to reduce artifacts
        H_conv1 = tf.image.resize_images(images=h0,
                                         size=tf.constant(
                                             [output1_shape[1], output1_shape[2]]),
                                         method=tf.image.ResizeMethod.NEAREST_NEIGHBOR)
        H_conv1 = tf.layers.conv2d(inputs=H_conv1, filters=s2, kernel_size=(
            5, 5), padding='same', activation=tf.nn.relu)
        H_conv1 = tf.contrib.layers.batch_norm(
            inputs=H_conv1, center=True, scale=True, is_training=True, scope="g_bn1")
        H_conv1 = tf.nn.leaky_relu(H_conv1)
        # Dimensions of H_conv1 = batch_size x 3 x 3 x 256 --> batchsize 64 64 256

        # Second DeConv Layer
        output2_shape = [batch_size, s4 - 1, s4 - 1, g_dim*2]
        # b_conv and W_conv's are unused --> deleted these
        H_conv2 = tf.image.resize_images(images=H_conv1,
                                         size=tf.constant(
                                             [output2_shape[1], output2_shape[2]]),
                                         method=tf.image.ResizeMethod.NEAREST_NEIGHBOR)
        # H_conv2 = tf.nn.conv2d_transpose(H_conv1, W_conv2, output_shape=output2_shape,
        #                                  strides=[1, 2, 2, 1], padding='SAME') + b_conv2
        H_conv2 = tf.layers.conv2d(inputs=H_conv2, filters=s4, kernel_size=(
            5, 5), padding='same', activation=tf.nn.relu)
        H_conv2 = tf.contrib.layers.batch_norm(
            inputs=H_conv2, center=True, scale=True, is_training=True, scope="g_bn2")
        H_conv2 = tf.nn.leaky_relu(H_conv2)
        # Dimensions of H_conv2 = batch_size x 6 x 6 x 128 --> batchsize 127 127 128

        # Third DeConv Layer
        output3_shape = [batch_size, s2 - 2, s2 - 2, g_dim*1]
        # b_conv and W_conv's are unused --> deleted these
        H_conv3 = tf.image.resize_images(images=H_conv2,
                                         size=tf.constant(
                                             [output3_shape[1], output3_shape[2]]),
                                         method=tf.image.ResizeMethod.NEAREST_NEIGHBOR)
        # H_conv3 = tf.nn.conv2d_transpose(H_conv2, W_conv3, output_shape=output3_shape,
        #                                  strides=[1, 2, 2, 1], padding='SAME') + b_conv3
        H_conv3 = tf.layers.conv2d(inputs=H_conv3, filters=s8, kernel_size=(
            5, 5), padding='same', activation=tf.nn.relu)
        H_conv3 = tf.contrib.layers.batch_norm(
            inputs=H_conv3, center=True, scale=True, is_training=True, scope="g_bn3")
        H_conv3 = tf.nn.leaky_relu(H_conv3)
        # Dimensions of H_conv3 = batch_size x 12 x 12 x 64 --> 1 254 254 64

        # Fourth DeConv Layer
        output4_shape = [batch_size, s, s, c_dim]
        # b_conv and W_conv's are unused --> deleted these
        H_conv4 = tf.image.resize_images(images=H_conv3,
                                         size=tf.constant(
                                             [output4_shape[1], output4_shape[2]]),
                                         method=tf.image.ResizeMethod.NEAREST_NEIGHBOR)
        # H_conv4 = tf.nn.conv2d_transpose(H_conv3, W_conv4, output_shape=output4_shape,
        #                                  strides=[1, 2, 2, 1], padding='VALID') + b_conv4
        H_conv4 = tf.layers.conv2d(inputs=H_conv4, filters=1, kernel_size=(
            5, 5), padding='same', activation=tf.nn.relu) # this should have 'VALID' padding??
        H_conv4 = tf.nn.tanh(H_conv4)
        # Dimensions of H_conv4 = batch_size x 28 x 28 x 1 --> batch_size x 512 x 512 x 1

        # print('h0: ', np.shape(h0))
        # print('H_conv1: ', np.shape(H_conv1))
        # print('H_conv2: ', np.shape(H_conv2))
        # print('H_conv3: ', np.shape(H_conv3))
        # print('H_conv4: ', np.shape(H_conv4))

    return H_conv4


# # create and view a single (essentially randomly) generated image:
# sess = tf.Session()
# # changed from 100 --> want a 512*512 image
# z_dimensions = IMAGE_SIZE*IMAGE_SIZE
# z_test_placeholder = tf.placeholder(tf.float32, [None, z_dimensions])

# sample_image = generator(z_test_placeholder, 1, z_dimensions)
# test_z = np.random.normal(-1, 1, [1, z_dimensions])

# sess.run(tf.global_variables_initializer())
# temp = (sess.run(sample_image, feed_dict={z_test_placeholder: test_z}))

# my_i = temp.squeeze()
# plt.imshow(my_i, cmap='gray_r')
# plt.show()


### Training a GAN ###
# changed from 100 --> want a 512*512 image
z_dimensions = IMAGE_SIZE*IMAGE_SIZE
batch_size = BATCH_SIZE
# Since we changed our batch size (from 1 to 16), we need to reset our Tensorflow graph
tf.reset_default_graph()

sess = tf.Session()

# Placeholder for input images to the discriminator
x_placeholder = tf.placeholder(
    "float", shape=[None, IMAGE_SIZE, IMAGE_SIZE, 1])  # 28,28,1]) # <-- original shape (now 512x512x1)
# Placeholder for input noise vectors to the generator
z_placeholder = tf.placeholder(tf.float32, [None, z_dimensions])

# Dx will hold discriminator prediction probabilities for the real MNIST images
Dx = discriminator(x_placeholder)
# Gz holds the generated images
Gz = generator(z_placeholder, batch_size, z_dimensions)
# Dg will hold discriminator prediction probabilities for generated images
Dg = discriminator(Gz, reuse=True)

# ensure forward compatibility: function needs to have logits and labels args explicitly used
g_loss = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(
    logits=Dg, labels=tf.ones_like(Dg)))

d_loss_real = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(
    logits=Dx, labels=tf.ones_like(Dx)))
d_loss_fake = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(
    logits=Dg, labels=tf.zeros_like(Dg)))
d_loss = d_loss_real + d_loss_fake

tvars = tf.trainable_variables()
d_vars = [var for var in tvars if 'd_' in var.name]
g_vars = [var for var in tvars if 'g_' in var.name]

# print(tf.get_variable_scope().reuse)
d_adam = tf.train.AdamOptimizer(D_ALPHA)
g_adam = tf.train.AdamOptimizer(G_ALPHA)
trainerD = d_adam.minimize(d_loss, var_list=d_vars)
trainerG = g_adam.minimize(g_loss, var_list=g_vars)

sess.run(tf.global_variables_initializer())
# Create a saver object which will save all the variables
saver = tf.train.Saver()
# loop:
iterations = ITERATIONS
i = 0
while i < iterations*batch_size:
    print('starting iteration: ', i)
    z_batch = np.random.normal(-1, 1, size=[batch_size, z_dimensions])
    # print('i:', i, 'i+batch_size:', i+batch_size)
    real_image_batch = x_train[i:i+batch_size, :, :, :]

    _, dLoss = sess.run([trainerD, d_loss], feed_dict={
                        z_placeholder: z_batch, x_placeholder: real_image_batch})  # Update the discriminator
    _, gLoss = sess.run([trainerG, g_loss], feed_dict={
                        z_placeholder: z_batch})  # Update the generator
    i = i+batch_size
    if i % (batch_size*10) == 0:
        print('done batch ', i/batch_size)
    if i % (batch_size*20) == 0:
        print('saving checkpoint at batch ', i/batch_size)
        saver.save(sess, './checkpoints/GAN'+str(i/batch_size)) 

        print('saving image at batch ', i/batch_size)
        sample_image = generator(z_placeholder, 1, z_dimensions, True)
        z_batch = np.random.normal(-1, 1, size=[1, z_dimensions])
        temp = (sess.run(sample_image, feed_dict={z_placeholder: z_batch}))
        my_i = temp.squeeze()
        # plt.imshow(my_i, cmap='gray')
        # plt.show()

        # save the generated image as an image:
        my_i = (my_i+1)*255/2  # scale up to within 0 255
        print('!!!!!!!!!image array:', my_i)
        im = Image.fromarray(my_i)
        # print('!!!!!!!!!!!!image fromarray:', list(im.getdata()))
        im = im.convert('RGB')
        # print('!!!!!!!!!!!!!!!image rgb:', list(im.getdata()))
     # make sure we don't overwrite:
        import os
        if os.path.exists('./generated/generated_' + str(i/batch_size) + '.png'):
            import time
            im.save("./generated/generated_" + str(i/batch_size) +
                    "{}.png".format(int(time.time())), "PNG")
        else:
            im.save('./generated/generated_' +
                    str(i/batch_size) + '.png', "PNG")

print('done training and generation!')
# see restoreAndView.py if you want to restore the model
