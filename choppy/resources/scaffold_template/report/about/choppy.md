---
id: quick-intro
title: 快速指南：Choppy for Reproducible Omics Pipeline
sidebar_label: 快速指南
---
{% raw %}
> Author: Yechao Huang
>
> Email: 17210700095@fudan.edu.cn
>
> Date: 2019-01-18

# Choppy快速指南

## Pipeline 分析三步走

基于`Choppy平台`进行 Pipeline 分析十分简单高效，只需要三步即可轻松搞定(**点击进入[演示视频](http://kancloud.nordata.cn/2019-01-20-choppy.mp4)**)：

1. 登陆**[Choppy App Store](http://choppy.3steps.cn)**，挑选符合自己需求的 App，并安装
2. 准备 App 所需的 Samples 文件
3. 提交任务

## 使用 APP 提交任务

> 基于 choppy 封装的 app 可以使得用户可以通过自定义或者下载的 `app` 简单快速的进行可重复并且可溯源的任务提交

- 选择所要使用的 **app** 并生成相应的 **samples.csv** 文件（以 dna-germline-0.1.0 为例）

  ```bash
  choppy samples dna-germline-0.1.0 --output dna-germline.csv
  ```

  通过上述命令会生成一个对应于使用的 app 的一个 .csv 格式文件，按照表头的内容将所涉及到的变量（如：fastq 文件在 OSS 上的路径、对应的 sample 的名字、sample_id 等）填入到文件中（注意以 “,” 进行分隔），在填写的过程中可以直接在 linux 系统下进行操作也可以下载到本地 PC 上使用 excel 进行操作。

  > sample_id : 对于每一个提交的样本名会根据 sample_id 来创建一个目录，里面包含了当前样本所运行时使用的 wdl 文件以及 input 文件，以便于对样本任务的溯源工夫

- 根据生成的 samples.csv 文件批量提交任务

  ```bash
  choppy batch dna-germline-0.1.0 samples.csv --project-name project
  ```

  当出现如下所示的信息时，表明当前任务提交成功：

  ```bash
  Sample ID: 1, Workflow ID: a6a24b7d-bea3-48fe-93f6-7b7aa8ce9b5f
  Successed: 1, /home/huangyechao/project/submitted.csv
  ```

  其中，第一行为所提交的样本的名字以及每一个样本对应的 workflow ID ，可用于查询该任务的运行状态；当有多个样本时，会有多行出现。
  第二行为统计 app 端成功的样本数，并且会生成包含有当次任务成功提交时的所有信息
  第三行为为统计 app 端失败的样本数（若没有失败则不会产生）

- 根据生成的 Workflow ID 可以进行任务状态的查询，使用命令如下

  ```bash
  choppy query -s a6a24b7d-bea3-48fe-93f6-7b7aa8ce9b5f
  ```

  此时会显示出该样本任务的状态信息，当显示为 submitted 时，表示任务正在向云端及进行投递过程中； 显示为 Running 时，表示任务已经成功在云端运行；当显示为 Failed 时，表示任务运行失败。
  使用 **-m** 参数可以查看更多关于任务的日志信息：

  ```bash
  choppy query -s -m a6a24b7d-bea3-48fe-93f6-7b7aa8ce9b5f
  ```

- 当任务提交成功之后，可登陆到阿里云控制台中，在批量计算的作业列表中查询任务的运行情况；通常当任务提交到阿里云计算平台时，会需要几分钟的服务器配置时间之后任务才会开始进行计算。

## 构建属于自己 WDL

在构建 **WDL** 之前，需要先对 **WDL** 的基本结果有一定的了解，其基本结构包含以下部分：`workflow`，`task`，`call`, `command`以及`output`（详见[WDL Base Structure](https://software.broadinstitute.org/wdl/documentation/structure)）

以下是对构建 **WDL** 脚本的一个简单教程（以 [Sentieon](http://goldenhelix.com/products/sentieon/index.html) 的 DNA-seq 为例）：

## 单个 task 的构建

- **command**： 通常我们在构建**pipeline** 时，是将每一步分析写入到一个脚本中，并调用脚本的方式串行使用，如下所示：

  ```bash
  $SENTIEON_INSTALL_DIR/bin/bwa mem -M -R "@RG\tID:$group\tSM:$sample\tPL:$pl" -t $nt $fasta $fastq_1 $fastq_2 | $SENTIEON_INSTALL_DIR/bin/sentieon util sort -o ${sam}.sorted.bam -t $nt --sam2bam -i -
  ```

  以上为 **DNA-seq** 中比对的命令，在 **WDL** 中这部分将会书写在 `command` 部分，如下所示：

  ```
  command <<<
  		set -o pipefail
  		set -e
  		export SENTIEON_LICENSE=此处替换为你的license
  		nt=$(nproc)
  		${SENTIEON_INSTALL_DIR}/bin/bwa mem -M -R "@RG\tID:${group}\tSM:${sample}\tPL:${pl}" -t $nt ${ref_dir}/${fasta} ${fastq_1} ${fastq_2} | ${SENTIEON_INSTALL_DIR}/bin/sentieon util sort -o ${sample}.sorted.bam -t $nt --sam2bam -i -
  >>>
  ```

  可以看到在 **WDL** 中，就是将日常所使用的命令填入在 `command` 中，并用`{ }`或者`<<< >>>`进行引用（后者主要是在于有多个命令运行时使用）。

  > 注意: `${变量}`的形式是 **WDL** 所识别的变量，当命令中的变量是`$变量`的形式时，**WDL**是无法识别的，如例子中的 `$nt` 在之前已经对其进行了定义；

- **output**： `command` 部分完成之后，需要对于该命令的输出进行定义，比对的结果产生的文件为`${sample}.sorted.bam` 以及 `${sample}.sorted.bam.bai` ，因此需要在 `output` 中对结果的输出进行定义：

  ```bash
  output {
  		File sorted_bam = "${sample}.sorted.bam"
  		File sorted_bam_index = "${sample}.sorted.bam.bai"
  	}
  ```

  左边为当前 `task` 输出结果的命名，右边为所输出结果文件名，用 `" "` 进行引用；

  当有多个结果文件输出时，只有在 `output` 中进行了定义的结果文件才会输出，没有定义的将不会输出到结果目录中；

- **runtime**： 对于每一个 `task` 的运行环境需要进行定义，包括所使用的软件的 `docker`信息，所使用的服务器配置信息，以及服务器的系统盘以及数据盘大小：

  ```bash
  runtime {
  		dockerTag:docker
      	cluster: cluster_config
      	systemDisk: "cloud_ssd 40"
      	dataDisk: "cloud_ssd " + disk_size + " /cromwell_root/"
  	}
  ```

  `dockerTag` 为所使用的 `docker` 信息，此处以变量表示

  `cluster` 为运行命令是所选用的服务器实例信息（[参照阿里云服务器 ECS](https://help.aliyun.com/document_detail/25378.html?spm=a2c4g.11186623.6.545.8e452f98mSzIST)）

  `systemDisk` 为使用的系统盘的大小，默认为 cloud_ssd 40G

  `dataDisk` 为使用的数据盘的大小信息，默认类型为 `cloud_ssd` ，挂载点为 `/cromwell_root/`

  > 注意：在系统盘和数据盘的写法上，需注意不同的变量之间存在空格

- 在将 `command` 主体部分改写完成之后，需要在 `task` 中声明 `command` 中所使用的变量形式：

  ```bash
  task mapping {
  	File fastq_1
  	File fastq_2
  	File ref_dir
  	String fasta
  	String SENTIEON_INSTALL_DIR
  	String group
  	String sample
  	String pl
  	String docker
  	String cluster_config
  	String disk_size

  	command <<<
  		....
  	>>>
  	runtime {
  		...
  	}

  	output {
  		...
  	}
  }

  ```

  对于在 `task` 中所使用到的变量，都需要在 `task` 上面先进行声明，通常有两种形式 `File` 以及 `String`

## workflow 的构建

> `workflow` 应用于在所有的 `task` 构建完成之后，对于每个步骤进行调用以及每个步骤之间的依赖关系的一个说明，包括以下两个部分 `import`，`call`

```bash
import "./tasks/mapping.wdl" as mapping
import "./tasks/Metrics.wdl" as Metrics

workflow sentieon  {
	call mapping.mapping as mapping {
		input:
		SENTIEON_INSTALL_DIR=SENTIEON_INSTALL_DIR,
		group=sample,
		sample=sample,
		pl="ILLUMINAL",
		....
	}
	call Metrics.Metrics as Metrics {
		input:
		....
	}
}
```

- **import** ：表明构建的 `workflow` 中所需要使用的步骤信息，这部分内容可根据使用者分析过程中需要的内容进行自定义：

  ```bash
  import "./tasks/mapping.wdl" as mapping
  import "./tasks/Metrics.wdl" as Metrics
  import "./tasks/Dedup.wdl" as Dedup
  import "./tasks/deduped_Metrics.wdl" as deduped_Metrics
  import "./tasks/Realigner.wdl" as Realigner
  import "./tasks/BQSR.wdl" as BQSR
  import "./tasks/Haplotyper.wdl" as Haplotyper
  ```

  引号内的内容为所要调用的 `task` 信息， `as` 之后的内容（如 `mapping` `Dedup` 等为所定义的步骤的别名）在命名时，应尽量使得命名简单并能包含所需的信息

- **call** : 是对所引用的 `task` 中的变量进行传递以及对不同的步骤之间的依赖关系进行说明：

  ```bash
  call mapping.mapping as mapping {
  		input:
  		SENTIEON_INSTALL_DIR=SENTIEON_INSTALL_DIR,
  		group=sample,
  		sample=sample,
  		pl="ILLUMINAL",
  		fasta=fasta,
  		ref_dir=ref_dir,
  		fastq_1=fastq_1,
  		fastq_2=fastq_2,
  		docker=docker,
  		disk_size=disk_size,
  		cluster_config=cluster_config
  	}

  	call Metrics.Metrics as Metrics {
  		input:
  		SENTIEON_INSTALL_DIR=SENTIEON_INSTALL_DIR,
  		fasta=fasta,
  		ref_dir=ref_dir,
  		sorted_bam=mapping.sorted_bam,
  		sorted_bam_index=mapping.sorted_bam_index,
  		sample=sample,
  		docker=docker,
  		disk_size=disk_size,
  		cluster_config=cluster_config
  	}
  ```

  首先需要对 `call` 进行声明，`mapping.mapping as mapping` 中，第一个 `mapping` 是与 `import` 中的别名保持一致，第二个 `mapping` 是与 `task` 中使用的命名保持一致（`task mapping {...}`），第三个 `mapping` 是作为在 `workflow` 中的命名； `input` 是将 `task` 中所使用的变量进行定义，`=`左边是变量名，右边是对变量的赋值，当所使用的变量会重复使用时，可以将其继续以变量的形式进行声明，并在`call`的外部进行声明;

  在构建 `pipeline` 中，通常某步的输入文件是上一步的结果输出，在 `call` 中，可以通过对上一步结果文件的引用使得 `workflow` 能自动判别程序的依赖关系，并采取串行或者并行计算；如上所示，`Metrics` 的输入文件是上一步 `mapping` 的输出结果文件，因此在 `input` 中 `mapping.sorted_bam` 表明该步骤使用到 `mapping` 中的 `sorted_bam` 文件，因此只有当 `mapping` 这一步运行结束时，`Metrics` 才会启动运行。

- **变量声明**：在`workflow` 中，同样需要对 `call` 中没有赋值的变量进行声明：

  ```bash
  	File fastq_1
  	File fastq_2

  	String SENTIEON_INSTALL_DIR
  	String sample
  	String docker

  	File ref_dir
  	File dbmills_dir
  	File dbsnp_dir
  	String db_mills
  	String fasta
  	String dbsnp
  	String disk_size
  	String cluster_config
  ```

  类似于 `task` 中的变量声明方式，需要 `File` 及 `String` 声明变量类型， 对于 `workflow` 中的变量，都会在 `input` 中进行赋值；

- **input**： 在 WDL 中所使用的变量，都会在 `input` 文件中进行赋值。变量的读取规则为，在 `call` 的内部使用的变量如果在 `workflow` 中的变量声明中同样进行了定义，则变量的传递顺序为 `input` --> `workflow` 变量声明 --> `call` ，当没有在 `workflow` 中声明，则变量的传递顺序为 `input` --> `call`

  ```bash
  {
    "sentieon.fasta": "GRCh38.d1.vd1.fa",
    "sentieon.ref_dir": "oss://pgx-reference-data/GRCh38.d1.vd1/",
    "sentieon.dbsnp": "dbsnp_146.hg38.vcf",
    "sentieon.fastq_1": "oss://pgx-storage-backend/WGS_germline/WGC107658D_combined_R1.fastq.gz",
    "sentieon.SENTIEON_INSTALL_DIR": "/opt/sentieon-genomics",
    "sentieon.dbmills_dir": "oss://pgx-reference-data/GRCh38.d1.vd1/",
    "sentieon.db_mills": "Mills_and_1000G_gold_standard.indels.hg38.vcf",
    "sentieon.cluster_config": "OnDemand ecs.sn2ne.2xlarge img-ubuntu-vpc",
    "sentieon.docker": "localhost:5000/sentieon-genomics:v2018.08.01 oss://pgx-docker-images/dockers",
    "sentieon.dbsnp_dir": "oss://pgx-reference-data/GRCh38.d1.vd1/",
    "sentieon.sample": "WGC107658D",
    "sentieon.disk_size": "500",
    "sentieon.fastq_2": "oss://pgx-storage-backend/WGS_germline/WGC107658D_combined_R2.fastq.gz"
  }
  ```

  `input` 文件的生成可以使用 `womtool`(参见[womtool](https://github.com/broadinstitute/cromwell/releases/tag/36)使用), 同时也可使用 `womtool` 对所写的 **WDL** 进行验证。

  ```bash
  java -jar womtool.jar validate 2.wdl   ####WDL验证
  java -jar womtool.jar inputs 3step.wdl  ### 生成input文件生成
  ```

- **将 WDL 脚本封装成为 APP**：单个 **WDL** 文件撰写完成之后，可以通过简单的改写就可将 **WDL** 文件封装成为``choppy`中的 **APP** 使用，用于批量提交，改写规则如下：

  - 将`workflow` 中的 `workflow_name`变为变量引用形式：

    ```bash
    workflow {{ project_name }} {
       ...
    }
    ```

    在 `choppy` 中对于变量是通过 `{{ }}`的形式进行引用，此处 `project_name` 是在使用 **APP** 提交任务时定义的变量，可用于提交任务之后所生成的可追溯的文件；

  - 将 `input` 中的相应的 `project_name` （即上面所示例子中的 `sentieon` ）改为 `{{project_name}}` ；此外对于后面所需要改变的参数变量，可以使用 `{{ }}` 进行变量引用：

    ```bash
    {
    	"{{ project_name }}.fasta": "GRCh38.d1.vd1.fa",
    	"{{ project_name }}.ref_dir": "oss://pgx-reference-data/GRCh38.d1.vd1/",
    	"{{ project_name }}.dbsnp": "dbsnp_146.hg38.vcf",
    	"{{ project_name }}.fastq_1": "{{ read1 }}",
    	"{{ project_name }}.SENTIEON_INSTALL_DIR": "/opt/sentieon-genomics",
    	"{{ project_name }}.dbmills_dir": "oss://pgx-reference-data/GRCh38.d1.vd1/",
    	"{{ project_name }}.db_mills": "Mills_and_1000G_gold_standard.indels.hg38.vcf",
    	"{{ project_name }}.cluster_config": "{{ cluster if cluster != '' else 'OnDemand ecs.sn1ne.4xlarge img-ubuntu-vpc' }}",
    	"{{ project_name }}.docker": "localhost:5000/sentieon-genomics:v2018.08.01 oss://pgx-docker-images/dockers",
    	"{{ project_name }}.dbsnp_dir": "oss://pgx-reference-data/GRCh38.d1.vd1/",
    	"{{ project_name }}.sample": "{{ sample_name }}",
    	"{{ project_name }}.disk_size": "{{ disk_size }}",
    	"{{ project_name }}.regions": "{{ regions }}",
    	"{{ project_name }}.fastq_2": "{{ read2 }}"
    }
    ```
{{% endraw %}}
    至此整个 APP 封装完毕，可以在 `choppy` 中使用
