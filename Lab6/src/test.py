import torch
import torch.nn as nn
import torchvision
from diffusers import DDPMScheduler, UNet2DModel
from torch.utils.data import DataLoader
from dataloader import DiffusionLoader
from tqdm import tqdm
import torchvision.transforms as transforms
from PIL import Image
from evaluator import evaluation_model
import os

class ClassConditionedUnet(nn.Module):
    def __init__(self, num_classes=24, class_emb_size=128, 
    blocks = [0, 1, 1], channels = [1, 2, 2]): #Default setting as tutorial
        super().__init__()
        first_channel = class_emb_size//4
        down_blocks = ["DownBlock2D" if x == 0 else "AttnDownBlock2D" for x in blocks]
        up_blocks = ["UpBlock2D" if x == 0 else "AttnUpBlock2D" for x in reversed(blocks)]
        channels = [first_channel * x for x in channels]
        self.model = UNet2DModel(
            sample_size = 64,
            in_channels = 3,
            out_channels = 3,
            layers_per_block = 2,
            block_out_channels = (channels), 
            down_block_types=(down_blocks),
            up_block_types=(up_blocks),
        )
        self.model.class_embedding = nn.Linear(num_classes, class_emb_size)

    def forward(self, x, t, label):
        return self.model(x, t, label).sample

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Using device:", device)

timesteps = 2000
ckpt = 'ckpt_v2/100.pth'

test_set = DiffusionLoader(json_file = 'json/test.json')
new_test_set = DiffusionLoader(json_file = 'json/new_test.json')

test_loader = DataLoader(test_set, batch_size = 1, shuffle = False)
new_test_loader = DataLoader(new_test_set, batch_size = 1, shuffle = False)

noise_scheduler = DDPMScheduler(num_train_timesteps=timesteps, beta_schedule='squaredcos_cap_v2')

model = ClassConditionedUnet(class_emb_size = 512, blocks = [0, 0, 0, 0, 0, 0], channels = [1, 1, 2, 2, 4, 4]).to(device)
checkpoint = torch.load(ckpt)
model.load_state_dict(checkpoint['model_state_dict'])
eval_model = evaluation_model()

model.eval()

# test.json
count = 0
all_images = []
accuracys = []
generating = []

for y in test_loader:
    os.makedirs('images/test', exist_ok=True)
    y = y.to(device)
    x = torch.randn(1, 3, 64, 64).to(device)
    for i, t in tqdm(enumerate(noise_scheduler.timesteps)):

        with torch.no_grad():
            y = y.squeeze(1)
            residual = model(x, t, y)

        x = noise_scheduler.step(residual, t, x).prev_sample
        if count == 0 and i % (timesteps // 10) == 0:
            generating.append(x.detach().cpu().squeeze(0))

    accuracy = eval_model.eval(x, y)
    accuracys.append(accuracy)
    print(f'image {count}  accuracy: {accuracy}')
    
    img = x.detach().cpu().squeeze(0)    
    if count == 25:
        generating.append(img)
        tensor_images = torch.stack(generating)
        row_image = torchvision.utils.make_grid(tensor_images, nrow=len(generating), padding=2)
        row_image_pil = transforms.ToPILImage()(row_image)
        row_image_pil.save('images/test/test_generating.png')
        row_image = torchvision.utils.make_grid(tensor_images, nrow=len(generating), padding=2, normalize=True)
        row_image_pil = transforms.ToPILImage()(row_image)
        row_image_pil.save('images/test/test_generating_normalized.png')
    
    all_images.append(img)

    img_grid = torchvision.utils.make_grid(img, nrow=len(img), padding=2, normalize=True)
    img_pil = transforms.ToPILImage()(img_grid)
    img_pil.save(f'images/test/{count}.png')
    count += 1

grid_image = torchvision.utils.make_grid(all_images, nrow=8, padding=2, normalize=True)
grid_image_pil = transforms.ToPILImage()(grid_image)
grid_image_pil.save('images/test/test_result.png')



print('Test Accuracy:')
print(sum(accuracys)/len(accuracys))
print()

# new_test.json
count = 0
all_images = []
accuracys = []
generating = []

for y in new_test_loader:
    os.makedirs('images/new_test', exist_ok=True)
    y = y.to(device)
    x = torch.randn(1, 3, 64, 64).to(device)
    for i, t in tqdm(enumerate(noise_scheduler.timesteps)):

        with torch.no_grad():
            y = y.squeeze(1)
            residual = model(x, t, y)

        x = noise_scheduler.step(residual, t, x).prev_sample
        if count == 0 and i % (timesteps // 10) == 0:
            generating.append(x.detach().cpu().squeeze(0))

    accuracy = eval_model.eval(x, y)
    accuracys.append(accuracy)
    print(f'image {count}  accuracy: {accuracy}')
    
    img = x.detach().cpu().squeeze(0)
    if count == 0: 
        generating.append(img)
        tensor_images = torch.stack(generating)
        row_image = torchvision.utils.make_grid(tensor_images, nrow=len(generating), padding=2)
        row_image_pil = transforms.ToPILImage()(row_image)
        row_image_pil.save('images/new_test/new_test_generating.png')
        row_image = torchvision.utils.make_grid(tensor_images, nrow=len(generating), padding=2, normalize=True)
        row_image_pil = transforms.ToPILImage()(row_image)
        row_image_pil.save('images/new_test/new_test_generating_normalized.png')

    all_images.append(img)
    
    img_grid = torchvision.utils.make_grid(img, nrow=len(img), padding=2, normalize=True)
    img_pil = transforms.ToPILImage()(img_grid)
    img_pil.save(f'images/new_test/{count}.png')
    count += 1

grid_image = torchvision.utils.make_grid(all_images, nrow=8, padding=2, normalize=True)
grid_image_pil = transforms.ToPILImage()(grid_image)
grid_image_pil.save('images/new_test/new_test_result.png')

print('New Test Accuracy:')
print(sum(accuracys)/len(accuracys))