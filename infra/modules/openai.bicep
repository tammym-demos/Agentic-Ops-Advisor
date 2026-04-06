// Azure OpenAI module — DEPRECATED
//
// This module is no longer used. The GPT-4.1 deployment is now hosted
// directly on the AI Foundry Hub (CognitiveServices AIServices) as a
// child deployment resource.
//
// See infra/modules/aifoundry.bicep for the current architecture:
//   - Hub: Microsoft.CognitiveServices/accounts (kind: AIServices)
//   - Model: Microsoft.CognitiveServices/accounts/deployments (child)
//   - Project: Microsoft.CognitiveServices/accounts/projects (child)
//
// This file is kept as a stub for historical reference but should not
// be included in main.bicep deployments.
