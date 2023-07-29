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

def assign_nested_value(nested_dict, keys_string, value):
    keys = keys_string.split('.')
    current_dict = nested_dict

    for key in keys[:-1]:  # We iterate until the penultimate key
        if key.endswith('[]'):  # The key refers to a list
            key = key.rstrip('[]')  # Remove the '[]' sign from the key
            if key not in current_dict or not isinstance(current_dict[key], list):  # If the key doesn't exist or it's not a list, we create an empty list
                current_dict[key] = []
            if not current_dict[key] or not isinstance(current_dict[key][-1], dict):  # If the list is empty or the last element is not a dictionary, we append an empty dictionary
                current_dict[key].append({})
            current_dict = current_dict[key][-1]  # We go one level down to the last dictionary in the list
        else:
            if key not in current_dict:  # If the key doesn't exist, we create an empty dict
                current_dict[key] = {}
            current_dict = current_dict[key]  # We go one level down

    if keys[-1].endswith('[]'):  # The last key refers to a list
        keys[-1] = keys[-1].rstrip('[]')  # Remove the '[]' sign from the key
        if keys[-1] not in current_dict or not isinstance(current_dict[keys[-1]], list):  # If the key doesn't exist or it's not a list, we create an empty list
            current_dict[keys[-1]] = []
        current_dict[keys[-1]].append(value)  # We append the value to the list
    else:
        current_dict[keys[-1]] = value  # We assign the value to the last key

    return nested_dict

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
def processDatasets(datasetNum, imageDirectory):
    # Extract xml data for this dataset
    mappedEMMetadata = extract_values(datasetXmlMap, xmlMetadata, datasetNum)
    
    # Read data from image in proper folder
    datasetName = datasetNames[datasetNum - 1]
    for root, dirs, files in os.walk(imageDirectory):
        if os.path.basename(root) == datasetName:
            for file in files:
                if file.endswith('.tif'):
                    imgPath = os.path.join(root, file)
                    break
            break
    imageData = readFile(imgPath)
    formattedMetadata = formatMetadata(imageData)
    imageMetadata = extractImageData(formattedMetadata, datasetImgMap)
    mappedImgMetadata = headerMapping(imageMetadata, datasetImgMap)
    
    return {**mappedEMMetadata, **mappedImgMetadata}

datasetMetadata = []
for i, dataset in enumerate(datasetNames[:2]):
    logging.info(i, dataset)
    datasetMetadata.append(processDatasets(i+1, imgDirectory))


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
                    imgPath = os.path.join(root, file)
                    break
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
    datasetMetadataDict, ImageMetadataDict =  processDatasets(i+1, imgDirectory)
    print(f'This is the current dataset: {dataset}.')
    datasetMetadataDict['acquisition.dataset[].entry.datasetType'] = dataset
    
    # Determine number of images in each dataset
    datasetMetadataDict['acquisition.dataset[].entry.numberOfItems'] = acqMetadata['acquisition.genericMetadata.numberOfCuts']
    print(datasetMetadataDict)
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
            try:
                nested_keys.remove('dataset')
            except:
                nested_keys.remove('dataset[]')
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
def save_metadata_as_json(metadata, save_path):
    with open(os.path.join(save_path, 'output.json'), 'w') as file:
        json.dump(metadata, file, indent=4)
    logging.info(f"Metadata saved as {save_path}")

    
def fixBooleans(d):
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, str):
                v = v.lower().strip()
                if v == 'on' or v == 'yes':
                    d[k] = True
                elif v == 'off' or v == 'no':
                    d[k] = False
            elif isinstance(v, list):
                for i in range(len(v)):
                    v[i] = fixBooleans(v[i])
            else:
                d[k] = fixBooleans(v)
    elif isinstance(d, list):
        for i in range(len(d)):
            d[i] = fixBooleans(d[i])
    return d

def cleanMetadata(nestedDict):
    x1 = assign_nested_value(nestedDict, 'acquisition.dataset[].entry.definition', 'acquisition_dataset')
    x2 = assign_nested_value(x1, 'acquisition.dataset[].entry.numberOfItems', '')
    x3 = assign_nested_value(x2, 'acquisition.dataset[].entry.images[].entry.definition', 'acquisition_image')
    x4 = fixBooleans(x3)
    return x4

combinedMetadata = combineMetadata(acqMetadata, datasetMetadata, imageMetadata)
cleanedMetadataDict = cleanMetadata(combinedMetadata)
save_metadata_as_json(cleanedMetadataDict, outputFile)
shutil.rmtree(tempDir)
