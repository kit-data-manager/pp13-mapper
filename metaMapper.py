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
    """
    extracts files of zip to a temporary directory
    :param zip_file_path: local file path to zip file
    :return: (path to contained emxml file, path to tmp dir) or (None, None) if no emxml file was found
    """
    temp_dir = tempfile.mkdtemp()

    start_time = time.time()  # Start time
    logging.info(f"Extracting {zip_file_path}...")

    target_dir = None

    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        total_items = len(zip_ref.namelist())

        for index, file_name in enumerate(zip_ref.namelist(), start=1):
            # if index%10 == 0:
            #     print(f"Extracting file {index}/{total_items}...")
            file_path = os.path.join(temp_dir, file_name)
            zip_ref.extract(file_name, temp_dir)

            # Look for file has the .emxml extension and designate the directory it's within as the target directory
            if file_name.endswith('.emxml') and target_dir is None: #TODO: this uses exactly the first emxml file found and explicitely ignores others. Correct behaviour?
                target_dir = os.path.dirname(file_path)

    if target_dir is None:
        logging.info("No .emxml file found in the zip file.")
        shutil.rmtree(temp_dir)
        return None, None

    end_time = time.time()  # End time
    total_time = end_time - start_time

    logging.info(f"Total time taken to process: {total_time:.2f} seconds. The target directory is {target_dir}.")
    return target_dir, temp_dir

def getExampleImage(directory):
    """
    Gets first tif file of provided dir path
    :param directory: directory path string
    :return: file path string
    """
    for file in os.listdir(directory):
        if file.endswith('.tif'):
            return os.path.join(directory, file)

def processImage(imgPath, mappingDict):
    """
    handles processing of an image based on mapping information
    :param imgPath: path to image file
    :param mappingDict: dict of path mappings for images
    :return: TODO: ?
    """
    # read image file
    rawImgMetadata = readFile(imgPath)
    formattedMetadata = formatMetadata(rawImgMetadata)
    metadata = extractImageData(formattedMetadata, mappingDict)
    mappedImgMetadata = headerMapping(metadata, mappingDict)

    return mappedImgMetadata

def processDatasets(datasetNum, imageDirectory, mappingDict):
    """
    handles processing of dataset
    :param datasetNum: index of dataset
    :param imageDirectory: path to image files
    :param mappingDict: dict of path mappings for images
    :return: TODO: ?
    """
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
    imageData = readFile(imgPath) #TODO: what happens if imgPath is not set above? When does this happen?
    formattedMetadata = formatMetadata(imageData)
    metadata = extractImageData(formattedMetadata, datasetImgMap)
    mappedImgMetadata = headerMapping(metadata, datasetImgMap)

    # Repeat to produce list of image metadata dictionaries
    #TODO: this method was defined twice, once with the following lines and once without, not returning imageMetadataList. Why?
    imageMetadataList = []
    for root, dirs, files in os.walk(imageDirectory):
        if os.path.basename(root) == datasetName:
            for file in files:
                if file.endswith('.tif'):
                    imgPath = os.path.join(root, file)
                    imageMetadataList.append(processImage(imgPath, mappingDict))

    return {**mappedEMMetadata, **mappedImgMetadata}, imageMetadataList


def combineMetadata(acquisition_metadata, dataset_metadata, image_metadata):
    """
    #TODO: seems to do a lot, investigate
    :param acquisition_metadata: dict of acquisition metadata
    :param dataset_metadata: dict of dataset metadata
    :param image_metadata: dict of image metadata
    :return: #TODO: ?
    """
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
    for ds in dataset_metadata:
        dataset_dict = {}
        for key, value in ds.items():
            nested_keys = key.split('.')
            nested_keys.remove('acquisition')
            try:
                nested_keys.remove('dataset')
            except: #TODO: make exception more specific
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

def parseNumericValues(metadata):
    """
    applies conversion to numeric values on all metadata entries
    :param metadata: metadata dict
    :return: None
    """
    for key, value in metadata.items():
        if isinstance(value, dict):
            # Recursive call for nested dictionaries
            parseNumericValues(value)
        elif isinstance(value, list):
            # Iterate through the list, applying parseNumericValues to each item if it's a dictionary
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    parseNumericValues(item)
                else:
                    # Attempt conversion for non-dictionary items in the list
                    value[i] = convertToNumeric(item)
        else:
            # Attempt conversion for non-list, non-dictionary items
            metadata[key] = convertToNumeric(value)

def convertToNumeric(value):
    """
    converts to float if possible or to int if possible or keeps as is
    :param value: value to convert
    :return: converted value or original value
    """
    try:
        # Try converting to float first
        numeric_value = float(value)
        # If the float is actually an int, convert it to int
        if numeric_value.is_integer():
            return int(numeric_value)
        else:
            return numeric_value
    except (ValueError, TypeError):
        # If conversion fails, return the original value
        return value

def save_metadata_as_json(metadata, save_path):
    """
    writes dict to file
    :param metadata: metadata dict
    :param save_path: output file path
    :return: None
    """
    with open(save_path, 'w') as file:
        json.dump(metadata, file, indent=4)
    logging.info(f"Metadata saved as {save_path}")

# # For local tests
# def save_metadata_as_json(metadata, save_path):
#     with open(os.path.join(save_path, 'output.json'), 'w') as file:
#         json.dump(metadata, file, indent=4)
#     logging.info(f"Metadata saved as {save_path}")

def fixBooleans(d):
    """
    Converts values representing boolean values to bool
    :param d: dict to traverse and convert
    :return: dict after conversion #TODO: why is this not void if it modifies the input anyway?
    """
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

def assign_nested_value(nested_dict, keys_string, value):
    """
    #TODO: check what this does exactly
    :param nested_dict:
    :param keys_string:
    :param value:
    :return: #TODO: Why is this not void? Does return the modified input?
    """
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

def cleanMetadata(nestedDict):
    """
    postprocess metadata for cleanup
    :param nestedDict: dict to traverse and clean
    :return: cleaned metadata #TODO: Why is this not void? Does return the modified input?
    """
    x1 = assign_nested_value(nestedDict, 'acquisition.dataset[].definition', 'acquisition_dataset')
    x2 = assign_nested_value(x1, 'acquisition.dataset[].numberOfItems', '')
    x3 = assign_nested_value(x2, 'acquisition.dataset[].images[].definition', 'acquisition_image')
    x4 = fixBooleans(x3)
    return x4

mapFile    = sys.argv[1]
inputZip   = sys.argv[2]
outputFile = sys.argv[3]

#make log level configurable from ENV, defaults to info level
logging.basicConfig(
    level=os.environ.get('LOGLEVEL', 'INFO').upper()
)

mainDir, tempDir = extract_zip_file(inputZip)
if not mainDir:
    logging.error("Mandatory emxml file not found. Aborting mapping")
    exit(1)
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

# Read and format image metadata
imgMappings = extractImageMappings(mapFile)

datasetMetadata = []
for i, dataset in enumerate(datasetNames[:2]):
    #logging.info(i, dataset)
    datasetMetadataDict, _ = processDatasets(i+1, imgDirectory, imgMappings)
    datasetMetadata.append(datasetMetadataDict)

datasetMetadata = []
imageMetadata   = []
for i, dataset in enumerate(datasetNames[:-1]):
    #logging.info(i, dataset)
    datasetMetadataDict, ImageMetadataDict =  processDatasets(i+1, imgDirectory, imgMappings)
    print(f'This is the current dataset: {dataset}.')
    datasetMetadataDict['acquisition.dataset[].datasetType'] = dataset

    # Determine number of images in each dataset
    datasetMetadataDict['acquisition.dataset[].numberOfItems'] = acqMetadata['acquisition.genericMetadata.numberOfCuts']
    print(datasetMetadataDict)
    datasetMetadata.append(datasetMetadataDict)
    imageMetadata.append(ImageMetadataDict)

combinedMetadata = combineMetadata(acqMetadata, datasetMetadata, imageMetadata)
parseNumericValues(combinedMetadata)
cleanedMetadataDict = cleanMetadata(combinedMetadata)
save_metadata_as_json(cleanedMetadataDict, outputFile)
shutil.rmtree(tempDir)
