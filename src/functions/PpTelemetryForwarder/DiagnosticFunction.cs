using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using System.Net;

namespace PpTelemetryForwarder;

public static class DiagnosticFunction
{
    [Function("HealthCheck")]
    public static HttpResponseData Run(
        [HttpTrigger(AuthorizationLevel.Admin, "get")] HttpRequestData req)
    {
        var response = req.CreateResponse(HttpStatusCode.OK);
        response.Headers.Add("Content-Type", "text/plain");

        var info = new System.Text.StringBuilder();
        info.AppendLine("Worker alive: true");
        info.AppendLine($"Time: {DateTimeOffset.UtcNow:O}");
        info.AppendLine($"EVENTHUB_CONNECTION_STRING set: {!string.IsNullOrEmpty(Environment.GetEnvironmentVariable("EVENTHUB_CONNECTION_STRING"))}");
        info.AppendLine($"EVENTHUB_CONNECTION_STRING starts with: {Environment.GetEnvironmentVariable("EVENTHUB_CONNECTION_STRING")?[..Math.Min(30, Environment.GetEnvironmentVariable("EVENTHUB_CONNECTION_STRING")?.Length ?? 0)]}");
        info.AppendLine($"KEYVAULT_URI: {Environment.GetEnvironmentVariable("KEYVAULT_URI")}");
        info.AppendLine($"PP_TENANT_ID: {Environment.GetEnvironmentVariable("PP_TENANT_ID")}");
        info.AppendLine($"UAMI_CLIENT_ID: {Environment.GetEnvironmentVariable("UAMI_CLIENT_ID")}");

        response.WriteString(info.ToString());
        return response;
    }
}
