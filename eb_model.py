import pytorch_lightning as pl
import transformers
import torch.nn.functional as F
import torch

class ClassModel(pl.LightningModule):

    def __init__(self, class_nums, bert_model="TurkuNLP/bert-base-finnish-cased-v1", **config):
        super().__init__()
        self.bert=transformers.BertModel.from_pretrained(bert_model)
        self.cls_layers=torch.nn.ModuleDict({name: torch.nn.Linear(self.bert.config.hidden_size, len(lst)) for name, lst in class_nums.items()})
        self.train_acc=torch.nn.ModuleDict({name: pl.metrics.Accuracy() for name in class_nums})
        self.val_acc=torch.nn.ModuleDict({name: pl.metrics.Accuracy() for name in class_nums})
        self.config=config


    def forward(self,batch):
        enc=self.bert(input_ids=batch['input_ids'],
                      attention_mask=batch['attention_mask'],
                      token_type_ids=batch['token_type_ids']) #BxS_LENxSIZE; BxSIZE
        return {name: layer(enc.pooler_output) for name, layer in self.cls_layers.items()}

    def training_step(self,batch,batch_idx):
        out = self(batch)
        losses=[]
        pbar={}
        for name in self.cls_layers:
            loss=F.cross_entropy(out[name],batch[name])
            losses.append(loss)
            acc=self.train_acc[name](out[name],batch[name])
            self.log(f'train_acc_{name}',acc*100)
            self.log(f'train_loss_{name}',loss)
            pbar["acc_"+name]=f"{acc*100:03.1f}"
        return {"loss":sum(losses),"progress_bar":pbar}

    def validation_step(self,batch,batch_idx):
        out = self(batch)
        for name in self.cls_layers:
            loss=F.cross_entropy(out[name],batch[name])
            self.val_acc[name](out[name],batch[name])

    def validation_epoch_end(self,_):
        for name in self.cls_layers:
            self.log(f"val_acc_{name}",self.val_acc[name].compute()*100)
            self.val_acc[name].reset()

    def configure_optimizers(self):
        optimizer = transformers.optimization.AdamW(self.parameters(), lr=self.config["lr"])
        scheduler = transformers.optimization.get_linear_schedule_with_warmup(optimizer, num_warmup_steps=int(self.config["num_training_steps"]*0.1), num_training_steps=self.config["num_training_steps"])
        scheduler = {'scheduler': scheduler, 'interval': 'step', 'frequency': 1}
        return [optimizer], [scheduler]
