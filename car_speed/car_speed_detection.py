import cv2
import time
import os
import re
import shutil
import math
import numpy as np
import pandas as pd
import tensorflow.keras
import matplotlib.pyplot as plt

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense
from tensorflow.keras.optimizers import Adam


# read_path and write_path all must exist
# this function will clear out all files in write path before writing to it
# return how many jpg files have been write
def read(read_path, write_dir):
    # Check if read_path and write_dir exist
    if not os.path.exists(read_path):
        print(f"read path: '{read_path}' doesn't exist")
        return False
    if not os.path.exists(write_dir):
        print(f"write directory: '{write_dir}' doesn't exist")
        return False
    # Check if write_dir is a directory
    if not os.path.isdir(write_dir):
        print(f"write directory: '{write_dir}' is not a directory")
        return False
    # Check if input format is mp4
    if not re.search(r'.*\.mp4', read_path):
        print(f"please input a mp4 file")
        return False

    # Start read the video
    # Clear out the content in that directory first
    shutil.rmtree(write_dir)
    os.makedirs(write_dir)
    # Make sure the write_dir end with '/', so later could add index for each jpg file
    if write_dir[-1] != '/':
        write_dir += '/'

    cap = cv2.VideoCapture(read_path)  # read in the video
    index = 0
    while cap.isOpened():  # read the video frame by frame
        ret, frame = cap.read()
        if not ret:
            break
        # write jpg file in write_dir
        cv2.imwrite(write_dir + str(index) + '.jpg', frame)
        index += 1
        if index % 1000 == 0:
            print(index)
    cap.release()
    cv2.destroyAllWindows()

    # return how many jpg have been read
    return index


# Check if images in the directory match image_count
def check_images_match(read_dir, image_count):
    # Check if read directory exists
    if not os.path.exists(read_dir):
        print(f"read directory: '{read_dir}' doesn't exist")
        return False
    # Check if read is a directory
    if not os.path.isdir(read_dir):
        print(f"read directory: '{read_dir}' is not a directory")
        return False

    # Make sure the read_dir end with '/', so later could add index for each jpg file
    if read_dir[-1] != '/':
        read_dir += '/'

    for index in range(0, image_count):
        if not os.path.exists(read_dir + str(index) + '.jpg'):
            return False
    return True


def slice_matrix(mag_matrix, x_slice, y_slice):
    # Calculate the sum of each mag area and return the sqrt of the area sum
    height, width = mag_matrix.shape
    height_seg_len = height // y_slice
    width_seg_len = width // x_slice
    result = []
    for h in range(y_slice):
        for w in range(x_slice):
            mag_area_sum = np.sum(
                mag_matrix[h * height_seg_len:(h+1) * height_seg_len, w * width_seg_len:(w+1) * width_seg_len])
            result.append(round(math.sqrt(mag_area_sum), 2))  # round the sqrt to 2

    return result


# calculate_optical_mag will convert the images to grayscale before calculating the optical flow
def calculate_optical_mag(image1, image2):
    # Check if image have the same size
    if image1.shape != image2.shape:
        print("Image has different size")
        return False

    # Convert image to grayscale to reduce noise
    image1 = cv2.cvtColor(image1, cv2.COLOR_BGR2GRAY)
    image2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)

    # Calculate the optical flow, the return vector is in Cartesian Coordinates
    flow = cv2.calcOpticalFlowFarneback(image1, image2, None, 0.5, 3, 15, 3, 5, 1.2, 0)

    # Extract the magnitude of each vector by transforming Cartesian Coordinates to Polar Coordinates
    mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    # normalize the magnitude
    mag_matrix = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)

    return mag_matrix


# Preprocess all the images in read_dir, output a .txt file(output_path) containing optical flow matrix
# for each frame with corresponding speed
def preprocess(read_dir, train_path, output_path, resize=0.5, x_slice=8, y_slice=6):
    start = time.time()  # start counting the preprocess time
    # Check if read directory exists
    if not os.path.exists(read_dir):
        print(f"read directory: '{read_dir}' doesn't exist")
        return False
    # Check if read is a directory
    if not os.path.isdir(read_dir):
        print(f"read directory: '{read_dir}' is not a directory")
        return False
    # Check if training path exists
    if not os.path.exists(train_path):
        print(f"training path: '{train_path}' doesn't exist")
        return False

    # Check if images in read_dir have same size as train_path
    f = open(train_path, 'r')
    training_list = f.read().split('\n')
    f.close()

    # Check if the images in directory match the length of the training list
    if not check_images_match(read_dir, len(training_list)):
        print(f"images in directory {read_dir} doesn't match the length of training list")
        return False

    # Write the first row, from 0 to partX * partY, and 'weight'
    f = open(output_path, 'w')
    cols = [str(i) for i in range(x_slice * y_slice)]
    cols.append('weight\n')
    cols_str = ', '.join(str(i) for i in cols)
    f.write(cols_str)

    # Reference:https://docs.opencv.org/3.4/d4/dee/tutorial_optical_flow.html
    # read in the first image and resize it
    if read_dir[-1] != '/':
        read_dir += '/'
    image1 = cv2.imread(read_dir + '0' + '.jpg')
    height, width, _ = image1.shape
    image1 = cv2.resize(image1, (int(width*resize), int(height*resize)))

    for index in range(1, len(training_list)):
        image2 = cv2.imread(read_dir + str(index) + '.jpg')
        height, width, _ = image2.shape
        image2 = cv2.resize(image2, (int(width * resize), int(height * resize)))

        mag_matrix = calculate_optical_mag(image1, image2)
        optical_mag_list = slice_matrix(mag_matrix, x_slice, y_slice)

        optical_mag_string = ', '.join(str(i) for i in optical_mag_list)
        f.write(optical_mag_string)  # write the magnitude of the optical flow
        f.write(', ' + training_list[index-1] + '\n')  # write the magnitude of the optical flow

        if index == len(training_list)-1:
            f.write(optical_mag_string)  # write the magnitude of the optical flow
            f.write(', ' + training_list[index] + '\n')  # write the magnitude of the optical flow

        if index % 1000 == 0:  # print out the index every 1000 images
            print(index)
        image1 = image2
    f.close()

    print("Preprocessed Time: ", time.time()-start)
    return time.time()-start


def get_dataset(read_path, split, shuf=True):
    if split > 1 or split < 0:
        print("split parameter out of range (0, 1)")
        return False, False, False, False
    if not os.path.exists(read_path):
        print(f"read path: '{read_path}' doesn't exist")
        return False, False, False, False

    # Read in csv file and shuf the data if needed
    np.random.seed(10)
    reader = pd.read_csv(read_path)
    dataset = reader.values
    if shuf:
        np.random.shuffle(dataset)
    row, column = dataset.shape
    column -= 1

    X = dataset[:, 0:column]
    Y = dataset[:, column]
    # Assign training and testing data
    split_line = int(row*split)
    X_train, Y_train = X[:split_line], Y[:split_line]
    X_test, Y_test = X[split_line:], Y[split_line:]
    return X_train, Y_train, X_test, Y_test


def train(read_path, validation_split=0.75, batch_size=128, epoch=100, verbose=1):
    # Check if read_path and write_dir exist
    if not os.path.exists(read_path):
        print(f"read path: '{read_path}' doesn't exist")
        return False
    X_train, Y_train, X_test, Y_test = get_dataset(read_path, validation_split, shuf=True)

    # Build a Sequential Model
    model = Sequential([
        Dense(units=512, input_shape=(X_train.shape[1],), activation='relu'),
        Dense(units=256, activation='relu'),
        Dense(units=512, activation='relu'),
        Dense(units=256, activation='relu'),
        Dense(units=128, activation='relu'),
        Dense(1)
    ])
    print(model.summary())

    model.compile(optimizer="adam", loss="mse", metrics=["mse"])
    model.fit(X_train, Y_train, epochs=epoch, batch_size=batch_size, verbose=verbose)
    mse, mae = model.evaluate(X_test, Y_test)
    print("MSE: %.2f" % mse)
    print("MAE_test: ", mae)
    model.save("Model.h5")

    return mse



# Plot Scatter still problem
def plot_scatter(prediction_data_path, real_data_path):
    # Check if model and video exist
    if not os.path.exists(prediction_data_path):
        print(f"prediction data path: '{prediction_data_path}' doesn't exist")
        return False
    if not os.path.exists(real_data_path):
        print(f"real data path : '{real_data_path}' doesn't exist")
        return False
    # Check if input format is .txt and .txt
    if not re.search(r'.*\.txt', prediction_data_path):
        print(f"please input a .txt file for prediction_data_path")
        return False
    if not re.search(r'.*\.txt', real_data_path):
        print(f"please input a .txt file for real_data_path")
        return False

    f = open(prediction_data_path, 'r')
    prediction_data = f.read().split('\n')
    f.close()

    f = open(real_data_path, 'r')
    real_data = f.read().split('\n')
    f.close()

    if len(prediction_data) != len(real_data):
        print("length of prediction_data and real_data are not the same")
        return False

    plt.plot([0, 100], [0, 100], 'red')
    plt.scatter(prediction_data, real_data)
    plt.title('Scatter plot for prediction data and real data')
    plt.xlabel('prediction_data')
    plt.ylabel('real_data')
    print(np.arange(0, 101, step=10))
    plt.xticks(np.arange(0, 101, 10))
    plt.yticks(np.arange(0, 101, 10))
    plt.show()

    pass


# read video and output frame by frame
def speed_detection(model_path, video, output_path, required_x_slice, required_y_slice):
    start = time.time()  # start counting the speed_detection
    # Check if model and video exist
    if not os.path.exists(model_path):
        print(f"model path: '{model_path}' doesn't exist")
        return False
    if not os.path.exists(video):
        print(f"video: '{video}' doesn't exist")
        return False
    # Check if input format is .h5 and .mp4
    if not re.search(r'.*\.h5', model_path):
        print(f"please input a h5 file for model")
        return False
    if not re.search(r'.*\.mp4', video):
        print(f"please input a mp4 file for video")
        return False
    model = tensorflow.keras.models.load_model(model_path)  # load the model

    f = open(output_path, 'w')
    cap = cv2.VideoCapture(video)  # read in the video
    ret, image1 = cap.read()
    index = 0
    while cap.isOpened():  # read the video frame by frame
        ret, image2 = cap.read()
        if not ret:
            break
        images_to_predict = calculate_optical_mag(image1, image2, required_x_slice, required_y_slice)  # !!!
        images_to_predict = np.array(images_to_predict)
        images_to_predict = images_to_predict.reshape(1, -1)
        predictions = model.predict(x=images_to_predict)[0][0]
        f.write(str(predictions) + '\n')
        print(predictions)
        index += 1
        print(index)

    f.write(str(predictions)) # copy the last one again cause the frame difference
    index += 1
    f.close()
    cap.release()
    cv2.destroyAllWindows()
    
    # return how many speed for frame has been outputted
    prediction_time = time.time() - start
    print("prediction time: ", prediction_time)
    print("image processed: ", index)
    return index, prediction_time


if __name__ == '__main__':
    # read('Data/train.mp4', 'Data/Car_Detection_images/')
    # preprocess('Data/Car_Detection_images', 'train.txt', 'Data/feature.txt')
    # train('Data/feature.txt')
    # speed_detection('Model.h5', 'Data/train_test.mp4', 'train_test_output.txt', 8, 6)

    plot_scatter('prediction_data.txt', 'real_data.txt')