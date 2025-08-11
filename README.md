# AI-Compliance-Inspector

求人票のコンプライアンス違反を検出するマルチエージェントAIシステム

## 📖 概要

AI-Compliance-Inspectorは、求人票の内容が法的コンプライアンス要件を満たしているかを自動的にチェックするマルチエージェントシステムです。このプロジェクトは、Azure AI Agentsと Azure OpenAI Service を活用し、以下のコンプライアンス違反を検出します：

- **出会い系サクラ募集の検出**: 直接的な表現を避けて記載された疑似的な求人の識別
- **男女雇用機会均等法違反の検出**: 性別による差別的表現や制限の識別
- **コンプライアンス違反の是正提案**: 検出された違反に対する修正案の生成

## ⚠️ 重要な注意事項

このプロジェクトは**デモンストレーション目的**で作成されており、様々なマルチエージェントパターンの実装を目的としています。そのため、パフォーマンスが最適化された設計とは限りません。本番環境での使用には、さらなる最適化とテストが必要です。

## 🏗️ アーキテクチャ

### マルチエージェント設計

このマルチエージェントアプリケーションは[ハンドオフ型](https://openai.github.io/openai-agents-python/handoffs/)のオーケストレーションを採用しています。
以下の専門エージェントで構成されています：

#### 1. **Triage Agent（トリアージエージェント）**

- **役割**: ユーザーからの入力を分析し、適切な専門エージェントにタスクを振り分け
- **機能**:
  - ユーザーの質問内容を解析
  - 適切な専門エージェントへのハンドオフ
  - 最終的な結果の統合と返答

#### 2. **Check Dating Scam Agent（出会い系チェックエージェント）**

- **役割**: 出会い系サービスのサクラ募集を偽装した求人の検出
- **機能**:
  - 直接的表現を避けた疑似的な求人文言の解析
  - Azure OpenAI Reasoning Modelを活用した高精度判定
  - 疑わしいパターンの識別

#### 3. **Check Gender Discriminatory Agent（性別差別チェックエージェント）**

- **役割**: 男女雇用機会均等法第5条違反の検出
- **機能**:
  - 性別による募集制限の検出
  - 職種名や条件での性別差別表現の識別
  - Azure AI Agentsを活用した法的知識の参照
- **チェック項目**:
  - 募集人数の性別比率記載
  - 性別ごとの異なる条件設定
  - 性別を指す職種名の使用
  - 明確な性別制限
  - 実質的な性別制限表現

#### 4. **Correction Agent（是正エージェント）**

- **役割**: 検出されたコンプライアンス違反の是正案提案
- **機能**:
  - 他エージェントの結果レビュー
  - 具体的な修正提案の生成
  - 法的要件を満たす代替表現の提示

### 技術スタック

- **フロントエンド**: Chainlit（チャットベースUI）
- **AIモデル**:
  - Azure OpenAI GPT-4.1（メインモデル）
  - Azure OpenAI o1-mini（推論モデル）
- **エージェントフレームワーク**:
  - [OpenAI Agent SDK](https://openai.github.io/openai-agents-python/)
  - Azure AI Foundry Agents
- **言語**: Python 3.12+

## 🛠️ セットアップ

### 前提条件

#### Azure リソースの作成

このプロジェクトを実行するには、以下のAzureリソースが必要です：

1. **Azure AI Foundry Project**
   - [Azure AI Foundry での AI プロジェクトの作成](https://learn.microsoft.com/ja-jp/azure/ai-studio/how-to/create-projects)
   - プロジェクトエンドポイントを取得

2. **Azure OpenAI Service**
   - [Azure OpenAI Service のリソース作成](https://learn.microsoft.com/ja-jp/azure/ai-services/openai/how-to/create-resource)
   - 以下のモデルデプロイが必要：
     - `gpt-4.1` または `gpt-4.1-mini`（メインモデル用）
     - `o4-mini`（推論モデル用）

3. **Azure AI Agents**
   - [Azure AI Agents の設定](https://learn.microsoft.com/ja-jp/azure/ai-services/agents/)
   - 性別差別知識エージェントの作成とAgent IDの取得
   - 本リポジトリでは以下のツールを指定
     - ナレッジベースとして [Azure AI Search のインデックスを事前構築](https://learn.microsoft.com/ja-jp/azure/ai-foundry/agents/how-to/tools/azure-ai-search?tabs=azurecli)
     - 外部検索ツールとして [Grounding with Bing Search を利用](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/tools/bing-grounding)

### 環境設定

#### 1. リポジトリのクローン

```bash
git clone https://github.com/ishidahra01/AI-Compliance-Inspector.git
cd AI-Compliance-Inspector
```

#### 2. Python環境の作成

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux
```

#### 3. 依存関係のインストール

```bash
pip install -r requirements.txt
```

#### 4. 環境変数の設定

`.env` ファイルを作成し、以下の値を設定：

```env
PROJECT_ENDPOINT=https://your-project-endpoint
GENDER_DISCRIMINATORY_KNOWLEDGE_AGENT_ID=your_agent_id

AZURE_OPENAI_API_KEY=your_azure_openai_api_key
AZURE_OPENAI_ENDPOINT=https://your-azure_openai-endpoint
AZURE_OPENAI_API_VERSION="2025-03-01-preview"
```

### 実行方法

```bash
cd src
chainlit run app.py
```

ブラウザで `http://localhost:8000` にアクセスしてチャットインターフェースを使用できます。

## 📝 使用方法

### 基本的な使い方

1. チャットインターフェースで求人票の内容を貼り付け（`data/` にダミーの求人票を格納している）
2. システムが自動的に適切なエージェントを選択
3. コンプライアンス違反の検出結果を確認
4. 必要に応じて是正案を要求

### 検出例

#### 出会い系サクラ募集の例

```text
【在宅OK／SNSオペレーター募集】エンタメ系チャットサポートで高収入！
- 自社運営のコミュニティサービス上で、ユーザーとのテキストチャット対応
- 完全歩合制（チャット接続時間・ユーザー満足度に応じてインセンティブ支給）
```

#### 性別差別の例

```text
【新規プロジェクトの営業マン大募集！】看護婦経験のある方優遇／女性のみ
- 女性のみ応募可（社内規定により）
- 看護婦経験のある方優遇
```

## 📁 プロジェクト構造

```text
AI-Compliance-Inspector/
├── src/
│   ├── app.py              # メインアプリケーション
├── data/                   # テストデータ
│   ├── violation_1.1.1.txt # 出会い系サクラ募集例
│   ├── violation_1.1.2.txt # 金融詐欺関連例
│   ├── violation_1.3.3.txt # 性別差別例
│   └── ...
├── requirements.txt        # Python依存関係
├── .env                   # 環境変数（.env.exampleをコピー要作成）
└── README.md
```

## 📄 ライセンス

このプロジェクトのライセンスについては、[LICENSE](LICENSE) ファイルを参照してください。

## 🔗 関連リンク

- [Azure AI Foundry Documentation](https://learn.microsoft.com/ja-jp/azure/ai-studio/)
- [Azure OpenAI Service Documentation](https://learn.microsoft.com/ja-jp/azure/ai-services/openai/)
- [Azure AI Agents Documentation](https://learn.microsoft.com/ja-jp/azure/ai-services/agents/)
- [Chainlit Documentation](https://docs.chainlit.io/)
- [男女雇用機会均等法（厚生労働省）](https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/koyoukintou/index.html)