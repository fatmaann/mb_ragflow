export enum LLMFactory {
  OpenRouter = 'OpenRouter',
  HuggingFace = 'HuggingFace',
  Builtin = 'Builtin',
}

// Please lowercase the file name
export const IconMap = {
  [LLMFactory.OpenRouter]: 'open-router',
  [LLMFactory.HuggingFace]: 'huggingface',
  [LLMFactory.Builtin]: 'builtin',
};
