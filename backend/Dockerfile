# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY Otthonra.Api/Otthonra.Api.csproj Otthonra.Api/
# proxy_ca is optional outside managed workspaces; never copied into an image layer.
RUN --mount=type=secret,id=proxy_ca \
    if [ -s /run/secrets/proxy_ca ]; then SSL_CERT_FILE=/run/secrets/proxy_ca dotnet restore Otthonra.Api/Otthonra.Api.csproj; else dotnet restore Otthonra.Api/Otthonra.Api.csproj; fi
COPY Otthonra.Api/ Otthonra.Api/
RUN dotnet publish Otthonra.Api/Otthonra.Api.csproj -c Release -o /app --no-restore
FROM mcr.microsoft.com/dotnet/aspnet:8.0
WORKDIR /app
COPY --from=build /app .
ENV ASPNETCORE_HTTP_PORTS=8080
USER $APP_UID
EXPOSE 8080
ENTRYPOINT ["dotnet", "Otthonra.Api.dll"]
