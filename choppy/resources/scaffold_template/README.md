> Author： Huang Yechao
> 
> E-mail：1721070009@fudan.edu.cn
> 
> Git: http://choppy.3steps.cn/huangyechao/target-germline.git
> 
> Last Updates: 16/1/2019

## 安装指南
```
# 激活choppy环境
source activate choppy-latest
# 安装app
choppy install LiXiangNan/hrd_score
```

## App概述
描述App解决了什么问题，适用范围与局限性。

示例：
![](http://kancloud.nordata.cn/2019-01-24-Screen%20Shot%202019-01-24%20at%2014.57.49.png)
![](http://kancloud.nordata.cn/2019-01-24-Screen%20Shot%202019-01-24%20at%2014.58.56.png)


## 流程与参数
此模块详细描述App包含的流程与参数，请参考[流程描述参考示例](https://software.broadinstitute.org/gatk/best-practices/workflow?id=11145)

参数指封装的软件所用到的参数，参数罗列可参考：
![](http://kancloud.nordata.cn/2019-01-24-Screen%20Shot%202019-01-24%20at%2015.05.21.png)

## 软件解决问题的思路
自研软件需要增加此模块内容，用于描述解决问题的思路。

## App输入变量与输入文件
自定义文件格式的务必给出文件格式的详细说明，如下链接所示：[文件格式描述参考示例](http://cole-trapnell-lab.github.io/cufflinks/file_formats/index.html)

输入变量是指定义在App中允许用户修改的值，可通过以下命令输出：

```
choppy samples <app_name>
```

此外，choppy支持定义默认值，App用户可通过以下命令修改defaults文件中定义的值。

```
choppy config --app-name <app_name> --key <key> --value <value>
```

App开发者定义在App中的变量，可同时在App的defaults文件中预设默认值。defaults文件是一个json文件，如下所示：

```
{
    "var_1": "value_1"
}
```

## App输出文件
输出文件务必给出文件格式的详细说明以及示例，如下链接所示：[文件格式描述参考示例](http://cole-trapnell-lab.github.io/cufflinks/file_formats/index.html)

## 结果展示与解读
GSEA结果解读示例：

> ### 1. Enrichment score（ES）
>
> ES是GSEA最初的结果，反应全部杂交data排序后，在此序列top或bottom富集的程度。
> ES原理：扫描排序序列，当出现一个功能集中的gene时，增加ES值，反之减少ES值，所以ES是个动态值。最终ES的确定是讲杂交数据排序序列所在位置定义为0，ES值定义为距离排序序列的最大偏差.
> - ES为正，表示某一功能gene集富集在排序序列前方
> - ES为负，表示某一功能gene集富集在排序序列后方。
> 图中的最高点为此通路的ES值，中间表示杂交数据的排序序列。竖线表示此通路中出现的芯片数据集中的gene。
>
> ### 2. NES
> 
> 由于ES是根据分析的数据集中的gene是否在一个功能gene set中出现来计算的，但各个功能gene set中包含的gene数目不同，且不同功能gene set与data之间的相关性也不同，因此，比较data set在不同功能gene set中的富集程度要对ES进行标准化处理，也就是NES
> NES=某一功能gene set的ES/数据集所有随机组合得到的ES平均值
> NES是主要的统计量。
> 
> ### 3. FDR
> 
> NES确定后，判断其中可能包含的错误阳性发现率。FDR=25%意味着对此NES的确定，4次可能错  1次。GSEA结果中，高亮显示FDR<25%的富集set。因为从这些功能gene中最可能产生有意义的假设，促进进一步研究。大多数情况下，选FDR<25%是合适的，但是，假如分析的芯片data set较少，选择的是探针随机组合而不是表型组合，若p不严格，那么应该选FDR<5%。一般而言，NES绝对值越大，FDR值就越小，说明富集程度高，结果可靠。
> 
> ### 4. 名义p值 nominal p-value
> 
> 描述的是针对某一功能gene子集得到的富集得分的统计显著性，显然，p越小，富集性越好。
> 
> **以上4个参数中，只有FDR进行了功能gene子集大小和多重假设检验矫正，而p值没有，因此，如果结果中有一个高度富集的功能gene子集，而其有很小的名义p-value和大的FDR意味着富集并不显著。**
> 
> 我的一个具体结果解读：
> 
> > 92/681 gene sets are  upregulated in PH
> > 0 gene sets are significantly enriched at FDR<25%
> > 1 gene sets are significantly enriched at n p-value <1%
> > 1 gene sets are significantly enriched at n p-value <5%
> 
> 在选择的BP中，有681个gene sets，92个PH中上调，其中75%的正确率支持0条子集上调，1个BP的gene表达上调名义p值<0.01。总体结果并不理想。
> 
> ### 5. 备注
> 
> #### GSEA富集结果太少说明：
> 
> 无gene set被富集。可能是因为分析的样本太少，关注的生物信息太微弱，或正在分析的功能集不能很好代表你所关心的生物过程，但仍然可以看下top ranked gene sets，这些信息可能会为你的假说提供微弱的证据。当然也可以尝试考虑分析其他gene sets，或增加samples
> 
> #### GSEA富集结果太多说明：
> 
> 太多的功能子集被富集了。可能是因为很多的gene sets代表同一生物信号，这可以在gene sets中查看leading edge sbusets来查看。或者也可以查看具体区别进行加工，比如samples来自不同labs，操作者不一样等。

## CHANGELOG
CHANGELOG参考示例：
![](http://kancloud.nordata.cn/2019-01-24-Screen%20Shot%202019-01-24%20at%2015.08.35.png)

## FAQ
FAQ参考示例：
![](http://kancloud.nordata.cn/2019-01-24-Screen%20Shot%202019-01-24%20at%2015.06.39.png)