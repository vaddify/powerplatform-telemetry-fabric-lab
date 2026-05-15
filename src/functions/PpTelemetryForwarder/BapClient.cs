using System.Net.Http.Json;
using System.Text.Json;
using Azure.Core;
using Azure.Identity;
using Azure.Security.KeyVault.Secrets;

namespace PpTelemetryForwarder;

/// <summary>
/// Thin wrapper over the Power Platform BAP REST surface.
/// Authenticates into the Power Platform tenant (which may differ from the
/// hosting Azure tenant) using a service principal whose secret is stored
/// in Key Vault and read via the function's user-assigned managed identity.
/// </summary>
public sealed class BapClient
{
    private const string PowerPlatformResource = "https://service.powerapps.com/.default";
    private const string PowerPlatformApiResource = "https://api.powerplatform.com/.default";
    private const string BapBaseUrl = "https://api.bap.microsoft.com";
    private const string PowerPlatformApiBaseUrl = "https://api.powerplatform.com";
    private const string ApiVersion = "2021-04-01";
    private const string PpApiVersion = "2022-03-01-preview";

    private readonly HttpClient _http;
    private readonly TokenCredential _credential;

    public BapClient(IHttpClientFactory httpFactory)
    {
        _http = httpFactory.CreateClient(nameof(BapClient));
        _http.BaseAddress = new Uri(BapBaseUrl);

        var ppTenantId = Environment.GetEnvironmentVariable("PP_TENANT_ID");
        var ppClientId = Environment.GetEnvironmentVariable("PP_CLIENT_ID");
        var secretName = Environment.GetEnvironmentVariable("PP_CLIENT_SECRET_NAME") ?? "pp-tenant-sp-secret";
        var keyVaultUri = Environment.GetEnvironmentVariable("KEYVAULT_URI");
        var uamiClientId = Environment.GetEnvironmentVariable("UAMI_CLIENT_ID");

        if (string.IsNullOrEmpty(ppTenantId) || string.IsNullOrEmpty(ppClientId) || string.IsNullOrEmpty(keyVaultUri))
        {
            // Local-dev fallback: chained DefaultAzureCredential against the signed-in dev account.
            _credential = new DefaultAzureCredential();
            return;
        }

        var uamiCredential = string.IsNullOrEmpty(uamiClientId)
            ? new ManagedIdentityCredential()
            : new ManagedIdentityCredential(uamiClientId);

        var kv = new SecretClient(new Uri(keyVaultUri), uamiCredential);
        var secret = kv.GetSecret(secretName).Value.Value;

        _credential = new ClientSecretCredential(ppTenantId, ppClientId, secret);
    }

    public async Task<JsonElement> GetTenantLicenseUsageAsync(CancellationToken ct)
    {
        var token = await _credential.GetTokenAsync(
            new TokenRequestContext(new[] { PowerPlatformApiResource }), ct);

        using var req = new HttpRequestMessage(
            HttpMethod.Get,
            $"{PowerPlatformApiBaseUrl}/licensing/tenantCapacity?api-version={PpApiVersion}");
        req.Headers.Authorization = new("Bearer", token.Token);

        using var resp = await _http.SendAsync(req, ct);
        resp.EnsureSuccessStatusCode();
        return await resp.Content.ReadFromJsonAsync<JsonElement>(cancellationToken: ct);
    }

    public async Task<JsonElement> GetEnvironmentLifecycleEventsAsync(DateTimeOffset since, CancellationToken ct)
    {
        var token = await _credential.GetTokenAsync(
            new TokenRequestContext(new[] { PowerPlatformResource }), ct);

        var url = $"/providers/Microsoft.BusinessAppPlatform/scopes/admin/environments" +
                  $"?api-version={ApiVersion}&$expand=properties.lifecycleEvents" +
                  $"&$filter=properties/lastModifiedTime ge {since:O}";

        using var req = new HttpRequestMessage(HttpMethod.Get, url);
        req.Headers.Authorization = new("Bearer", token.Token);

        using var resp = await _http.SendAsync(req, ct);
        resp.EnsureSuccessStatusCode();
        return await resp.Content.ReadFromJsonAsync<JsonElement>(cancellationToken: ct);
    }
}
