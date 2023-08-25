from acquisitionMapper import extract_metadata_addresses, xml_to_dict, extract_values
from imageMapper import readFile, formatMetadata, extractImageMappings, extractImageData, headerMapping
from datasetMapper import extract_metadata_addresses_dataset
import os
import json
import zipfile
import tempfile
import shutil
import time
import sys
import logging

def extract_zip_file(zip_file_path):
    temp_dir = tempfile.mkdtemp()
    
    start_time = time.time()  # Start time
    logging.info("Extracting {zip_file_path}...")

    target_dir = None

    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        total_items = len(zip_ref.namelist())

        for index, file_name in enumerate(zip_ref.namelist(), start=1):
            # if index%10 == 0:
            #     print(f"Extracting file {index}/{total_items}...")
            file_path = os.path.join(temp_dir, file_name)
            zip_ref.extract(file_name, temp_dir)

            # Look for file has the .emxml extension and designate the directory it's within as the target directory
            if file_name.endswith('.emxml') and target_dir is None:
                target_dir = os.path.dirname(file_path)

    if target_dir is None:
        logging.info("No .emxml file found in the zip file.")
        return None, None

    end_time = time.time()  # End time
    total_time = end_time - start_time

    logging.info(f"Total time taken to process: {total_time:.2f} seconds. The target directory is {target_dir}.")
    return target_dir, temp_dir

mapFile    = sys.argv[1]
inputZip   = sys.argv[2]
outputFile = sys.argv[3]

def getExampleImage(directory):
    for file in os.listdir(directory):
        if file.endswith('.tif'):
            return os.path.join(directory, file)

mainDir, tempDir = extract_zip_file(inputZip)
imgFile = getExampleImage(os.path.join(mainDir, 'Images/SEM Image'))
imgDirectory = os.path.join(mainDir, 'Images')
xmlFile = os.path.join(mainDir, 'EMproject.emxml')

xmlMap, imgMap = extract_metadata_addresses(mapFile)
xmlMetadata = xml_to_dict(xmlFile)


acqXmlMetadata = extract_values(xmlMap, xmlMetadata)

# Read an image for acquisition metadata
imgMetadata = readFile(imgFile)
formattedImgMetadata = formatMetadata(imgMetadata)
extractedImgMetadata = extractImageData(formattedImgMetadata, imgMap)
acqImgMetadata = headerMapping(extractedImgMetadata, imgMap)

# The metadata for the acquisition is then the combined metadata from the xml file and an image
acqMetadata = {**acqXmlMetadata, **acqImgMetadata}


# Read and format dataset metadata
datasetXmlMap, datasetImgMap = extract_metadata_addresses_dataset(mapFile)
datasets = xmlMetadata['EMProject']['Datasets']['Dataset']
# print(f'len = {len(datasets)}, datasets: {datasets}')
if isinstance(datasets, list):
    datasetNames = [d['Name'] for d in datasets]
else:
    datasetNames = [datasets['Name']]

# def processDatasets(datasetNum, imageDirectory):
#     # Extract xml data for this dataset
#     mappedEMMetadata = extract_values(datasetXmlMap, xmlMetadata, datasetNum)
    
#     # Read data from image in proper folder
#     datasetName = datasetNames[datasetNum - 1]
#     for root, dirs, files in os.walk(imageDirectory):
#         if os.path.basename(root) == datasetName:
#             for file in files:
#                 if file.endswith('.tif'):
#                     global imgPath
#                     imgPath = os.path.join(root, file)
#                     print(f'Here is the image path: {imgPath}')
#                     break
#                 # else:
#                 #     print('Image path not assigned.')
#             break
#     imageData = readFile(imgPath)
#     formattedMetadata = formatMetadata(imageData)
#     imageMetadata = extractImageData(formattedMetadata, datasetImgMap)
#     mappedImgMetadata = headerMapping(imageMetadata, datasetImgMap)
    
#     return {**mappedEMMetadata, **mappedImgMetadata}

# datasetMetadata = []
# for i, dataset in enumerate(datasetNames[:2]):
#     logging.info(i, dataset)
#     datasetMetadata.append(processDatasets(i+1, imgDirectory))


# Read and format image metadata
imgMappings = extractImageMappings(mapFile)
def processImage(imgPath):
    # read image file
    rawImgMetadata = readFile(imgPath)
    formattedMetadata = formatMetadata(rawImgMetadata)
    imageMetadata = extractImageData(formattedMetadata, imgMappings)
    mappedImgMetadata = headerMapping(imageMetadata, imgMappings)
    
    return mappedImgMetadata


def processDatasets(datasetNum, imageDirectory):
    # Extract xml data for this dataset
    mappedEMMetadata = extract_values(datasetXmlMap, xmlMetadata, datasetNum)
    
    # Read data from image in proper folder
    datasetName = datasetNames[datasetNum - 1]
    for root, dirs, files in os.walk(imageDirectory):
        if os.path.basename(root) == datasetName:
            for file in files:
                if file.endswith('.tif'):
                    global imgPath
                    imgPath = os.path.join(root, file)
                    # print(f'Image path in processDatasets = {imgPath}')
                    break
                else:
                    print('imgPath in processDatasets not assigned.')
            break
    imageData = readFile(imgPath)
    formattedMetadata = formatMetadata(imageData)
    imageMetadata = extractImageData(formattedMetadata, datasetImgMap)
    mappedImgMetadata = headerMapping(imageMetadata, datasetImgMap)
    
    # Repeat to produce list of image metadata dictionaries
    imageMetadataList = []
    for root, dirs, files in os.walk(imageDirectory):
        if os.path.basename(root) == datasetName:
            for file in files:
                if file.endswith('.tif'):
                    imgPath = os.path.join(root, file)
                    imageMetadataList.append(processImage(imgPath))
    
    
    return {**mappedEMMetadata, **mappedImgMetadata}, imageMetadataList

datasetMetadata = []
imageMetadata   = []
for i, dataset in enumerate(datasetNames[:-1]):
    logging.info(i, dataset)
    print(dataset)
    datasetMetadataDict, ImageMetadataDict =  processDatasets(i+1, imgDirectory)
    datasetMetadata.append(datasetMetadataDict)
    imageMetadata.append(ImageMetadataDict)

def combineMetadata(acquisition_metadata, dataset_metadata, image_metadata):    
    metadata = {}
    # Combine acquisition metadata
    for key, value in acquisition_metadata.items():
        nested_keys = key.split('.')
        current_dict = metadata

        for nested_key in nested_keys[:-1]:
            if nested_key not in current_dict:
                current_dict[nested_key] = {}
            current_dict = current_dict[nested_key]

        current_dict[nested_keys[-1]] = value

    # Combine dataset metadata
    metadata['acquisition']['dataset'] = []
    for dataset in dataset_metadata:
        dataset_dict = {}
        for key, value in dataset.items():
            nested_keys = key.split('.')
            nested_keys.remove('acquisition')
            nested_keys.remove('dataset')
            current_dict = dataset_dict

            for nested_key in nested_keys[:-1]:
                if nested_key not in current_dict:
                    current_dict[nested_key] = {}
                current_dict = current_dict[nested_key]

            current_dict[nested_keys[-1]] = value

        metadata['acquisition']['dataset'].append(dataset_dict)

    # Combine image metadata
    for i, images in enumerate(image_metadata):
        metadata['acquisition']['dataset'][i]['images'] = []
        for image in images:
            image_dict = {}
            for key, value in image.items():
                nested_keys = key.split('.')
                nested_keys.remove('acquisition')
                nested_keys.remove('dataset')
                nested_keys.remove('images')
                current_dict = image_dict

                for nested_key in nested_keys[:-1]:
                    if nested_key not in current_dict:
                        current_dict[nested_key] = {}
                    current_dict = current_dict[nested_key]

                current_dict[nested_keys[-1]] = value

            metadata['acquisition']['dataset'][i]['images'].append(image_dict)
    return metadata

# def save_metadata_as_json(metadata, save_path):
#     with open(save_path, 'w') as file:
#         json.dump(metadata, file, indent=4)
#     logging.info(f"Metadata saved as {save_path}")

# # For local tests
#def save_metadata_as_json(metadata, save_path):
 #   with open(os.path.join(save_path, 'output.json'), 'w') as file:
  #      json.dump(metadata, file, indent=4)
   # logging.info(f"Metadata saved as {save_path}")


## create a pandas dataframe with the nested dictionary
# to copy the nested dictionaries to the right of the existing dataframe
def cross_join(left, right):
    new_rows = [] if right else left
    for left_row in left:
        for right_row in right:
            temp_row = deepcopy(left_row)
            for key, value in right_row.items():
                temp_row[key] = value
            new_rows.append(deepcopy(temp_row))
    return new_rows

# for flattening a nested list element by element
def flatten_list(data):
    for elem in data:
        if isinstance(elem, list):
            yield from flatten_list(elem)
        else:
            yield elem

# converts the nested json to a pandas Dataframe and correctly assign the value headers with full path with each level separated by a dot
def json_to_dataframe(data_in):
    def flatten_json(data, prev_heading=''):
        if isinstance(data, dict):
            rows = [{}]
            for key, value in data.items():
                rows = cross_join(rows, flatten_json(value, prev_heading + '.' + key))
        elif isinstance(data, list):
            rows = []
            for item in data:
                [rows.append(elem) for elem in flatten_list(flatten_json(item, prev_heading))]
        else:
            rows = [{prev_heading[1:]: data}]
        return rows

    return pandas.DataFrame(flatten_json(data_in))

# #  for use with the mapping service
# # convert the dataframe to csv and write it into a csv file
def save_metadata_as_csv(metadata, save_path):
    dataframe = json_to_dataframe(metadata)
    with open(save_path, 'w') as file:
        dataframe.to_csv(file, index=False)
    logging.info(f"CSV_Metadata saved in {save_path}")


# # for local tests
# # convert the dataframe to csv and write it into a csv file
# def save_metadata_as_csv(metadata, save_path):
#     dataframe = json_to_dataframe(metadata)
#     with open(os.path.join(save_path, 'metadata.csv'), 'w') as file:
#         dataframe.to_csv(file, index=False)
#     logging.info(f"CSV_Metadata saved in {save_path}")
#     print(f"CSV_Metadata saved in {save_path}")


combinedMetadata = combineMetadata(acqMetadata, datasetMetadata, imageMetadata)
save_metadata_as_csv(combinedMetadata, outputFile)
shutil.rmtree(tempDir)
