# horovodrun -np `nvidia-smi --list-gpus | wc -l` -H localhost:`nvidia-smi --list-gpus | wc -l` python examples/flex/keras/hvd_cifar10.py

import time

import keras
import numpy as np
from keras.datasets import cifar10
from keras.applications.resnet50 import ResNet50
from keras.preprocessing.image import ImageDataGenerator
import keras.utils
from skimage.transform import resize

import runai.flex

EPOCHS = 1
DATA_AUGMENTATION = True

runai.flex.init(global_batch_size=64, max_gpu_batch_size=16)

class StepTimeReporter(keras.callbacks.Callback):
    def on_batch_begin(self, batch, logs={}):
        self.start = time.time()

    def on_batch_end(self, batch, logs={}):
        print(' >> Step %d took %g sec' % (batch, time.time() - self.start))

    def on_epoch_begin(self, epoch, logs=None):
        self.epoch_start = time.time()

    def on_epoch_end(self, epoch, logs=None):
        print(' >> Epoch %d took %g sec time %g sec' % (epoch, time.time() - self.epoch_start, time.time() ))

# img_arr is of shape (n, h, w, c)
def resize_image_arr(img_arr):
    x_resized_list = []
    for i in range(img_arr.shape[0]):
        img = img_arr[i]
        resized_img = resize(img, (224, 224))
        x_resized_list.append(resized_img)
    return np.stack(x_resized_list)

(x_train, y_train), (x_test, y_test) = cifar10.load_data()

x_train = x_train[:2048]
y_train = y_train[:2048]
x_test = x_test[:2048]
y_test = y_test[:2048]

print("Resizing images")
x_train = resize_image_arr(x_train)
x_test = resize_image_arr(x_test)

# Convert class vectors to binary class matrices.
y_train = keras.utils.to_categorical(y_train, 10)
y_test = keras.utils.to_categorical(y_test, 10)

# Normalize the data
x_train = x_train.astype('float32')
x_test = x_test.astype('float32')
x_train /= 255
x_test /= 255

print("Building the model")
model = ResNet50(include_top=True, weights=None, classes=10)

# wrap 'model' with Run:AI elasticity
model = runai.flex.keras.models.Model(model)

model.compile(loss='categorical_crossentropy',
    optimizer=keras.optimizers.SGD(lr=1e-3),
    metrics=['accuracy']
)

if DATA_AUGMENTATION:
    datagen = ImageDataGenerator(
        featurewise_center=False,  # set input mean to 0 over the dataset
        samplewise_center=False,  # set each sample mean to 0
        featurewise_std_normalization=False,  # divide inputs by std of the dataset
        samplewise_std_normalization=False,  # divide each input by its std
        zca_whitening=False,  # apply ZCA whitening
        rotation_range=0,  # randomly rotate images in the range (degrees, 0 to 180)
        width_shift_range=0,  # randomly shift images horizontally (fraction of total width)
        height_shift_range=0,  # randomly shift images vertically (fraction of total height)
        horizontal_flip=True,  # randomly flip images
        vertical_flip=False)  # randomly flip images

    # Compute quantities required for feature-wise normalization
    # (std, mean, and principal components if ZCA whitening is applied).
    datagen.fit(x_train)

    # Fit the model on the batches generated by datagen.flow().
    model.fit_generator(datagen.flow(x_train, y_train,
                                        batch_size=runai.flex.batch_size),
                                        steps_per_epoch=int(10 * x_train.shape[0] / runai.flex.batch_size),
                        epochs=EPOCHS,
                        validation_data=(x_test, y_test),
                        workers=1,
                        callbacks=[StepTimeReporter()])
else:
    model.fit(x_train, y_train,
            batch_size=runai.flex.batch_size,
            epochs=EPOCHS,
            validation_data=(x_test, y_test),
            shuffle=False)

print("Done")
